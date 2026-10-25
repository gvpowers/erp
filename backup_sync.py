"""
GV Powers ERP - Remote Backup & Owner Server Synchronization.

Pushes immutable, append-only archive events to backup.gvpowers.in over HTTPS.

Design guarantees (see docs/BACKUP_API_CONTRACT.md):

* ERP DELETE != BACKUP DELETE. Only ``created`` / ``updated`` / ``deleted``
  operations exist. A deletion sends the full last-known snapshot plus
  DELETED_IN_ERP metadata; no operation can ever remove archive data.
* Every event carries a unique ``event_id`` (idempotent on the server).
* Events are written to a local outbox (``backup_events``) BEFORE delivery is
  attempted, and retried with exponential backoff. The ERP keeps working when
  the backup server is offline.
* Nothing in this module may ever raise into an ERP request: every public
  entry point swallows and logs its own errors.
* Secrets (API key) live in env vars first; a UI-entered key is stored
  encrypted at rest and never echoed back to any client.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import socket
import threading
import time
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import current_app, has_app_context
from sqlalchemy import func
from urllib import error as urlerror
from urllib import request as urlrequest

logger = logging.getLogger('gv.backup')

BACKUP_EVENT_STATUSES = ('pending', 'completed', 'failed')
OPERATIONS = ('created', 'updated', 'deleted')

DEFAULT_TIMEOUT_SECONDS = 6
DEFAULT_SYNC_INTERVAL_SECONDS = 60
MAX_ATTEMPTS = 12
BASE_BACKOFF_SECONDS = 30
MAX_BACKOFF_SECONDS = 3600
BATCH_LIMIT = 200

_LOCAL_HOSTS = ('localhost', '127.0.0.1', '::1', 'testserver', 'test.local')


# ---------------------------------------------------------------------------
# Configuration resolution (env vars win; Settings table is the fallback)
# ---------------------------------------------------------------------------

def _setting(key, default=None):
    try:
        return _get_app_module().get_setting(key, default)
    except Exception:
        return default


def _get_app_module():
    """Locate the live application module.

    Under ``python app.py`` the application runs as ``__main__``; doing a
    plain ``from app import ...`` here would re-execute app.py as a second
    module (and blow up under the running server). Prefer an already-loaded
    'app' module, fall back to '__main__', and only import as a last resort.
    """
    import sys
    for name in ('app', '__main__'):
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, 'get_setting'):
            return mod
    try:
        import app as app_mod
        if hasattr(app_mod, 'get_setting'):
            return app_mod
    except Exception:
        pass
    raise RuntimeError('GV Powers application module is not loaded')


def get_backup_url():
    """Resolve the archive URL: env var > Settings > environment default.

    Environment defaults keep local development and production working with
    the same code - only configuration changes between them:
      development -> http://127.0.0.1:8000
      production  -> https://backup.gvpowers.in
    """
    url = (os.getenv('BACKUP_API_URL')
           or os.getenv('BACKUP_BASE_URL')
           or os.getenv('DATABASE_APP_URL') or '').strip()
    if not url:
        url = (_setting('backup_api_url') or '').strip()
    if not url:
        environment = (os.getenv('ENVIRONMENT')
                       or os.getenv('APP_ENV') or 'development').lower()
        url = ('https://backup.gvpowers.in' if environment in ('production', 'prod')
               else 'http://127.0.0.1:8000')
    return url.rstrip('/')


def get_site_id():
    return (os.getenv('BACKUP_SITE_ID') or 'gvpowers-erp').strip()


def is_enabled():
    """Enabled = URL + key resolvable AND neither env nor Settings turned off."""
    if not get_backup_url() or not get_backup_key():
        return False
    env_flag = (os.getenv('BACKUP_ENABLED') or '').strip().lower()
    if env_flag in ('0', 'false', 'no', 'off'):
        return False
    setting_flag = (_setting('backup_enabled') or '').strip().lower()
    if setting_flag in ('0', 'false', 'no', 'off'):
        return False
    return True


def get_backup_key():
    """Resolve the API key: env var first, then the encrypted DB value."""
    env_key = (os.getenv('BACKUP_API_KEY') or '').strip()
    if env_key:
        return env_key
    stored = _setting('backup_api_key_enc') or ''
    if not stored:
        return ''
    return _decrypt_secret(stored)


# --- At-rest protection for a UI-entered key -------------------------------
# Derives a keystream from SECRET_KEY via HMAC-SHA256 (no extra dependencies).
# Env-var storage remains the recommended production path; this only protects
# against casual reads of the settings table.

def _derive_key():
    secret = current_app.config.get('SECRET_KEY', 'gv-powers') if has_app_context() else os.getenv('SECRET_KEY', 'gv-powers')
    return hashlib.sha256(('gv-backup|%s' % secret).encode('utf-8')).digest()


def encrypt_secret(plain):
    data = plain.encode('utf-8')
    nonce = os.urandom(16)
    key = _derive_key()
    stream = b''
    block = hmac.new(key, nonce, hashlib.sha256).digest()
    counter = 0
    while len(stream) < len(data):
        stream += block
        counter += 1
        block = hmac.new(key, nonce + str(counter).encode(), hashlib.sha256).digest()
    enc = bytes(a ^ b for a, b in zip(data, stream))
    return base64.urlsafe_b64encode(nonce + enc).decode('ascii')


def _decrypt_secret(token):
    try:
        raw = base64.urlsafe_b64decode(token.encode('ascii'))
        nonce, enc = raw[:16], raw[16:]
        key = _derive_key()
        stream = b''
        block = hmac.new(key, nonce, hashlib.sha256).digest()
        counter = 0
        while len(stream) < len(enc):
            stream += block
            counter += 1
            block = hmac.new(key, nonce + str(counter).encode(), hashlib.sha256).digest()
        return bytes(a ^ b for a, b in zip(enc, stream)).decode('utf-8')
    except Exception:
        return ''


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def _dump_json(payload):
    return json.dumps(payload, default=_json_default, ensure_ascii=False)


def _model_columns(model_obj):
    return {c.name: getattr(model_obj, c.name) for c in model_obj.__table__.columns}


def serialize_customer(c):
    d = _model_columns(c)
    return d


def serialize_product(p):
    d = _model_columns(p)
    return d


def serialize_supplier(s):
    return _model_columns(s)


def serialize_user(u):
    d = _model_columns(u)
    d.pop('password_hash', None)  # never ship credentials
    d.pop('otp_secret', None)
    return d


def serialize_payment(p):
    d = _model_columns(p)
    inv = getattr(p, 'invoice', None)
    if inv is not None:
        d['invoice_number'] = inv.invoice_number
        d['customer_id'] = inv.customer_id
    return d


def serialize_audit(a):
    d = _model_columns(a)
    u = getattr(a, 'user', None)
    if u is not None:
        d['username'] = u.username
    return d


def serialize_invoice(inv):
    """Invoice with embedded items (relationship-preserving snapshot)."""
    d = _model_columns(inv)
    d['items'] = [_model_columns(it) for it in (inv.items or [])]
    return d


def serialize_quotation(q):
    d = _model_columns(q)
    d['items'] = [_model_columns(it) for it in (q.items or [])]
    return d


def serialize_purchase_order(po):
    d = _model_columns(po)
    d['items'] = [_model_columns(it) for it in (po.items or [])]
    return d


SERIALIZERS = {
    'customer': serialize_customer,
    'product': serialize_product,
    'supplier': serialize_supplier,
    'purchase_order': serialize_purchase_order,
    'quotation': serialize_quotation,
    'invoice': serialize_invoice,
    'payment': serialize_payment,
    'user': serialize_user,
    'audit_log': serialize_audit,
}


# ---------------------------------------------------------------------------
# Event envelope construction
# ---------------------------------------------------------------------------

def _current_actor():
    try:
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            return {'id': current_user.id, 'username': current_user.username}
    except Exception:
        pass
    return None


def build_event(entity, operation, entity_id, data, previous_data=None,
                version=None, actor=None):
    """Build the full event envelope sent to the backup server."""
    now = datetime.utcnow()
    envelope = {
        'event_id': uuid.uuid4().hex,
        'site_id': get_site_id(),
        'entity': entity,
        'operation': operation,
        'entity_id': int(entity_id) if entity_id is not None else None,
        'version': int(version) if version else 1,
        'timestamp': now.isoformat(timespec='seconds') + 'Z',
        'actor': actor or _current_actor(),
        'data': data,
    }
    if previous_data is not None:
        envelope['previous_data'] = previous_data
    if operation == 'deleted':
        envelope['deletion'] = {
            'status': 'DELETED_IN_ERP',
            'deleted_at': envelope['timestamp'],
            'deleted_by': (envelope.get('actor') or {}).get('username'),
        }
    return envelope


# ---------------------------------------------------------------------------
# Outbox model access (model lives in app.py; late import avoids cycles)
# ---------------------------------------------------------------------------

def _backup_event_model():
    return _get_app_module().BackupEvent


def next_version(entity, entity_id):
    """Advisory version hint: 1 + number of prior create/update events."""
    try:
        BackupEvent = _backup_event_model()
        count = (BackupEvent.query
                 .filter(BackupEvent.entity_type == entity,
                         BackupEvent.entity_id == int(entity_id),
                         BackupEvent.operation.in_(('created', 'updated', 'deleted')))
                 .count())
        return int(count) + 1
    except Exception:
        return 1


# ---------------------------------------------------------------------------
# Public recording API -- safe to call from any route after a commit
# ---------------------------------------------------------------------------

def record_event(entity, operation, entity_id, data=None, previous_data=None,
                 deliver_now=True, defer_reason=None):
    """Queue (and best-effort deliver) one archive event. Never raises.

    The outbox row is committed first so the intent survives crashes; HTTP
    delivery happens afterwards and its failure only affects the queue.
    """
    try:
        if operation not in OPERATIONS:
            logger.warning('Refusing unknown backup operation %r', operation)
            return None
        if not is_enabled():
            return None
        serializer = SERIALIZERS.get(entity)
        if serializer is None:
            logger.warning('No serializer for backup entity %r', entity)
            return None
        if data is None:
            return None

        BackupEvent = _backup_event_model()
        envelope = build_event(entity, operation, entity_id, data,
                               previous_data=previous_data,
                               version=next_version(entity, entity_id))
        event = BackupEvent(
            event_id=envelope['event_id'],
            site_id=envelope['site_id'],
            entity_type=entity,
            entity_id=int(entity_id) if entity_id is not None else None,
            operation=operation,
            version=envelope['version'],
            payload=_dump_json(envelope),
            status='pending',
            attempt_count=0,
            next_attempt_at=datetime.utcnow(),
        )
        db = _get_app_module().db
        db.session.add(event)
        db.session.commit()

        if deliver_now:
            attempt_delivery(event)
        return event
    except Exception:
        try:
            db = _get_app_module().db
            db.session.rollback()
        except Exception:
            pass
        logger.exception('Failed to enqueue backup event %s/%s/%s',
                         entity, operation, entity_id)
        return None


def record_created(entity, entity_id, data=None, **kw):
    return record_event(entity, 'created', entity_id, data=data, **kw)


def record_updated(entity, entity_id, data=None, previous_data=None, **kw):
    return record_event(entity, 'updated', entity_id, data=data,
                        previous_data=previous_data, **kw)


def record_deleted(entity, entity_id, last_known_data, **kw):
    """Archive-safe deletion marker. ``last_known_data`` MUST be captured
    before the ERP row was deleted; it is preserved forever server-side."""
    kw.setdefault('deliver_now', True)
    return record_event(entity, 'deleted', entity_id, data=last_known_data, **kw)


def record_deferred(entity, operation, entity_id, data=None):
    """Queue without inline delivery (high-frequency entities like audit logs)."""
    return record_event(entity, operation, entity_id, data=data, deliver_now=False)


# ---------------------------------------------------------------------------
# HTTP layer (single choke point so tests can stub it)
# ---------------------------------------------------------------------------

def _http(method, url, api_key, body_bytes, timeout):
    """Perform one HTTP call. Returns (status_code:int, body:bytes)."""
    headers = {
        'Authorization': 'Bearer %s' % api_key,
        'X-GV-Site-Id': get_site_id(),
        'X-GV-Timestamp': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
        'Content-Type': 'application/json',
        'User-Agent': 'GVPowers-ERP-Backup/1.0',
    }
    if body_bytes:
        try:
            envelope = json.loads(body_bytes.decode('utf-8'))
            if isinstance(envelope, dict) and envelope.get('event_id'):
                headers['X-GV-Event-Id'] = str(envelope['event_id'])
        except Exception:
            pass
    req = urlrequest.Request(url, data=body_bytes if method == 'POST' else None,
                             headers=headers, method=method)
    with urlrequest.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def _classify_error(exc):
    if isinstance(exc, urlerror.HTTPError):
        code = exc.code
        detail = ''
        try:
            detail = exc.read(400).decode('utf-8', 'replace').strip()
        except Exception:
            pass
        mapping = {
            401: 'Authentication failed (invalid API key).',
            403: 'Access forbidden for this API key.',
            404: 'Backup endpoint not found (check Backup Server URL).',
            409: 'Duplicate event rejected by server.',
            429: 'Backup server rate-limited the request.',
        }
        friendly = mapping.get(code, 'Backup server returned HTTP %s.' % code)
        if detail and code in (400,):
            friendly += ' ' + detail[:200]
        retryable = code in (408, 409, 425, 429) or code >= 500
        return code, friendly, retryable
    if isinstance(exc, socket.timeout):
        return None, 'Connection timed out.', True
    if isinstance(exc, urlerror.URLError):
        reason = str(getattr(exc, 'reason', exc))
        if 'timed out' in reason.lower():
            return None, 'Connection timed out.', True
        if 'refused' in reason.lower():
            return None, 'Connection refused — backup server unreachable.', True
        if 'getaddrinfo' in reason.lower() or 'name or service' in reason.lower():
            return None, 'DNS lookup failed for the backup server.', True
        if 'SSL' in reason or 'certificate' in reason.lower():
            return None, 'TLS/SSL error connecting to the backup server.', True
        return None, 'Connection failed: %s' % reason[:160], True
    return None, 'Unexpected error: %s' % str(exc)[:160], False


def _assert_https(url):
    lowered = (url or '').lower()
    if lowered.startswith('https://'):
        return True, None
    if lowered.startswith('http://'):
        host = lowered.split('//', 1)[1].split('/', 1)[0].split(':', 1)[0]
        if host in _LOCAL_HOSTS:
            return True, None
        return False, 'Refusing to send backup data over plain HTTP.'
    return False, 'Backup Server URL must start with https://'


# ---------------------------------------------------------------------------
# Delivery + retries
# ---------------------------------------------------------------------------

def attempt_delivery(event):
    """One delivery pass for an outbox row. Never raises."""
    try:
        BackupEvent = _backup_event_model()
        url = get_backup_url()
        key = get_backup_key()
        ok_url, why = _assert_https(url)
        if not ok_url:
            _mark_event(event, success=False, message=why,
                        retryable=False, commit=True)
            _audit_exhausted_if_needed(event)
            return False

        status_code, body = _http(
            'POST', url + '/api/v1/events', key, event.payload.encode('utf-8'),
            timeout=int(os.getenv('BACKUP_TIMEOUT_SECONDS') or DEFAULT_TIMEOUT_SECONDS),
        )
        # 2xx => stored; 409 => duplicate event id => idempotent success.
        if 200 <= status_code < 300 or status_code == 409:
            _mark_event(event, success=True, message='', commit=True)
            return True
        _mark_event(event, success=False,
                    message='Backup server returned HTTP %s.' % status_code,
                    retryable=status_code in (409,) or status_code >= 500 or status_code == 429,
                    commit=True)
        _audit_exhausted_if_needed(event)
        return bool(200 <= status_code < 300)
    except Exception as exc:
        code, friendly, retryable = _classify_error(exc)
        try:
            _mark_event(event, success=False, message=friendly,
                        retryable=retryable, commit=True)
            _audit_exhausted_if_needed(event)
        except Exception:
            logger.exception('Could not persist backup delivery failure')
        return False


def _mark_event(event, success, message, retryable, commit=True):
    BackupEvent = _backup_event_model()
    now = datetime.utcnow()
    event.last_attempt_at = now
    if success:
        event.status = 'completed'
        event.delivered_at = now
        event.last_error = None
        event.next_attempt_at = None
    else:
        event.attempt_count = (event.attempt_count or 0) + 1
        event.last_error = message
        if not retryable:
            # Config-level problem (bad key, malformed payload): surface it
            # immediately in the Failed bucket instead of spinning retries.
            event.status = 'failed'
            event.next_attempt_at = None
        elif event.attempt_count >= MAX_ATTEMPTS:
            event.status = 'failed'
            event.next_attempt_at = None
        else:
            event.status = 'pending'
            delay = min(BASE_BACKOFF_SECONDS * (2 ** max(event.attempt_count - 1, 0)),
                        MAX_BACKOFF_SECONDS)
            event.next_attempt_at = now + timedelta(seconds=delay)
        _touch_connection_state(success=False, error=message)
    if commit:
        db = _get_app_module().db
        db.session.commit()


def _audit_exhausted_if_needed(event):
    """One audit row per event that exhausts retries (rare, important)."""
    try:
        if event.status != 'failed':
            return
        log_audit = _get_app_module().log_audit
        log_audit(None, 'BACKUP_EVENT_FAILED', 'backup_event', event.id,
                  '%s/%s #%s: %s' % (event.entity_type, event.operation,
                                     event.entity_id, (event.last_error or '')[:200]))
    except Exception:
        logger.debug('Could not audit BACKUP_EVENT_FAILED', exc_info=True)


def process_outbox(limit=BATCH_LIMIT, include_not_yet_due=True):
    """Deliver queued events. Returns summary dict. Never raises."""
    result = {'sent': 0, 'failed': 0, 'remaining': 0}
    try:
        BackupEvent = _backup_event_model()
        q = BackupEvent.query.filter(BackupEvent.status == 'pending')
        if not include_not_yet_due:
            q = q.filter(BackupEvent.next_attempt_at <= datetime.utcnow())
        events = q.order_by(BackupEvent.created_at).limit(limit).all()
        for ev in events:
            if attempt_delivery(ev):
                result['sent'] += 1
            else:
                result['failed'] += 1
        result['remaining'] = (BackupEvent.query
                               .filter(BackupEvent.status == 'pending').count())
        if result['sent']:
            _touch_connection_state(success=True)
            try:
                log_audit = _get_app_module().log_audit
                log_audit(None, 'BACKUP_SYNC_COMPLETED', 'backup_api', None,
                          'Auto/queued sync delivered %s event(s)' % result['sent'])
            except Exception:
                pass
        elif result['failed']:
            _touch_connection_state(success=False,
                                    error='Delivery failures during sync.')
        return result
    except Exception:
        logger.exception('process_outbox crashed')
        return result


def retry_failed(limit=BATCH_LIMIT):
    """Reset failed events back to pending and deliver them now."""
    summary = {'reset': 0, 'sent': 0, 'failed': 0}
    try:
        BackupEvent = _backup_event_model()
        rows = BackupEvent.query.filter(BackupEvent.status == 'failed')\
            .order_by(BackupEvent.created_at).limit(limit).all()
        for ev in rows:
            ev.status = 'pending'
            ev.attempt_count = 0
            ev.next_attempt_at = datetime.utcnow()
        db = _get_app_module().db
        db.session.commit()
        summary['reset'] = len(rows)
        if rows:
            outcome = process_outbox(limit=limit)
            summary['sent'] = outcome['sent']
            summary['failed'] = outcome['failed']
            try:
                log_audit = _get_app_module().log_audit
                log_audit(None, 'BACKUP_RETRY', 'backup_api', None,
                          'Manual retry: %s reset, %s delivered' %
                          (summary['reset'], summary['sent']))
            except Exception:
                pass
        return summary
    except Exception:
        logger.exception('retry_failed crashed')
        return summary


def manual_sync(limit=BATCH_LIMIT):
    """[Sync Now]: send all pending events immediately (due or not)."""
    try:
        summary = process_outbox(limit=limit, include_not_yet_due=True)
        try:
            log_audit = _get_app_module().log_audit
            log_audit(None, 'BACKUP_SYNC_COMPLETED', 'backup_api', None,
                      'Manual sync: %s delivered, %s failed, %s remaining'
                      % (summary['sent'], summary['failed'], summary['remaining']))
        except Exception:
            pass
        return summary
    except Exception:
        logger.exception('manual_sync crashed')
        return {'sent': 0, 'failed': 0, 'remaining': 0}


# ---------------------------------------------------------------------------
# Connection test (Phase 12) + status summary (Phase 13)
# ---------------------------------------------------------------------------

_connection_state = {'last_success_at': None, 'last_error': None}
_conn_lock = threading.Lock()


def _touch_connection_state(success, error=None):
    with _conn_lock:
        if success:
            _connection_state['last_success_at'] = datetime.utcnow()
            _connection_state['last_error'] = None
        else:
            _connection_state['last_error'] = error


def test_connection():
    """GET /api/v1/health -> (ok, message, latency_ms). Never raises."""
    url = get_backup_url()
    if not url:
        return False, 'Backup Server URL is not configured.', 0
    ok_url, why = _assert_https(url)
    if not ok_url:
        return False, why, 0
    started = time.monotonic()
    try:
        status, body = _http('GET', url + '/api/v1/health', get_backup_key(),
                             None,
                             timeout=int(os.getenv('BACKUP_TIMEOUT_SECONDS') or DEFAULT_TIMEOUT_SECONDS))
        latency = int((time.monotonic() - started) * 1000)
        if 200 <= status < 300:
            try:
                doc = json.loads(body.decode('utf-8'))
            except Exception:
                return False, 'Backup server returned a malformed response.', latency
            if str(doc.get('status', '')).lower() == 'ok':
                service = doc.get('service', 'gvpowers-backup')
                _touch_connection_state(success=True)
                return True, 'Connected (%s), %sms' % (service, latency), latency
            return False, 'Backup server reported an unhealthy status.', latency
        _, friendly, _ = _classify_error(urlerror.HTTPError(
            url, status, 'HTTP %s' % status, None, None))
        _touch_connection_state(success=False, error=friendly)
        return False, friendly, latency
    except Exception as exc:
        latency = int((time.monotonic() - started) * 1000)
        _, friendly, _ = _classify_error(exc)
        _touch_connection_state(success=False, error=friendly)
        return False, friendly, latency


def status_summary():
    """Everything the Settings -> Backup API panel renders."""
    try:
        BackupEvent = _backup_event_model()
        pending = BackupEvent.query.filter(BackupEvent.status == 'pending').count()
        failed = BackupEvent.query.filter(BackupEvent.status == 'failed').count()
        completed = BackupEvent.query.filter(BackupEvent.status == 'completed').count()
        last_err_row = (BackupEvent.query
                        .filter(BackupEvent.last_error.isnot(None))
                        .order_by(BackupEvent.last_attempt_at.desc())
                        .first())
    except Exception:
        pending = failed = completed = 0
        last_err_row = None

    with _conn_lock:
        last_success = _connection_state['last_success_at']
        runtime_error = _connection_state['last_error']

    enabled = is_enabled()
    url = get_backup_url()
    connected = bool(enabled and completed and last_success)
    return {
        'enabled': enabled,
        'configured': bool(url and get_backup_key()),
        'url_set': bool(url),
        'key_from_env': bool((os.getenv('BACKUP_API_KEY') or '').strip()),
        'connected': connected,
        'pending': pending,
        'failed': failed,
        'completed': completed,
        'last_success_at': last_success,
        'last_error': runtime_error or (last_err_row.last_error if last_err_row else None),
    }


# ---------------------------------------------------------------------------
# Background worker (Phase 10 automatic retries)
# ---------------------------------------------------------------------------

_worker_started = threading.Event()


def start_worker(app):
    """Daemon thread that drains due events periodically.

    Disabled automatically under tests (TESTING=1) and when
    BACKUP_SYNC_INTERVAL_SECONDS=0.
    """
    if _worker_started.is_set():
        return
    if (os.getenv('TESTING') or '').strip().lower() in ('1', 'true', 'yes'):
        return
    try:
        interval = int(os.getenv('BACKUP_SYNC_INTERVAL_SECONDS',
                                 str(DEFAULT_SYNC_INTERVAL_SECONDS)))
    except ValueError:
        interval = DEFAULT_SYNC_INTERVAL_SECONDS
    if interval <= 0:
        return

    def _loop():
        while True:
            time.sleep(interval)
            try:
                with app.app_context():
                    process_outbox(limit=50, include_not_yet_due=False)
            except Exception:
                logger.exception('Backup worker iteration failed')

    t = threading.Thread(target=_loop, name='gv-backup-sync-worker', daemon=True)
    t.start()
    _worker_started.set()
