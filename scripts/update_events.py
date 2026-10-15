#!/usr/bin/env python3
"""Build Blogger race data from initial verified snapshot, manual changes and permitted JSON feeds.

No runin.kr crawler is enabled or embedded: enable only a feed supplied with use rights.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DOCS = ROOT / 'docs'
FIELDS = ('title', 'run', 'start', 'end', 'fee', 'startPlace', 'officialLink', 'badgeText', 'source', 'registrationUrl', 'linkType', 'verifiedAt', 'registrationStatus', 'statusVerifiedAt', 'statusSourceUrl')
ALLOWED_STATUS = {'open', 'closed', 'upcoming', 'unknown', 'cancelled', ''}
ALLOWED_BADGES = {'접수중', '접수예정', '접수마감', '접수정보 없음', '공식확인', '취소', ''}
DATE = re.compile(r'^20\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$')
SAFE_URL = re.compile(r'^https?://[^\s<>"\']+$')


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else default


def canonical_title(value):
    s = str(value).lower()
    s = re.sub(r'20(?:25|26|27|28)', '', s)
    s = re.sub(r'제\s*\d+\s*회|\d+\s*회', '', s)
    s = re.sub(r'전국|국제|마라톤대회|마라톤|대회|경기', '', s)
    return re.sub(r'[\s·.,()\-_/&+]', '', s)


def event_key(e):
    return e['run'] + '|' + canonical_title(e['title'])


def date_value(value):
    value = str(value or '').strip()
    if not value:
        return ''
    if not DATE.fullmatch(value):
        raise ValueError(f'날짜 형식 오류: {value!r} (YYYY-MM-DD)')
    datetime.strptime(value, '%Y-%m-%d')
    return value


def normalize(raw, provenance=''):
    if not isinstance(raw, dict):
        raise ValueError('대회 항목은 JSON 객체여야 합니다')
    title = str(raw.get('title') or raw.get('name') or '').strip()
    run = date_value(raw.get('run') or raw.get('date'))
    if not title or not run:
        raise ValueError(f'대회명이나 개최일이 없습니다: {raw}')
    url = str(raw.get('officialLink') or '').strip()
    if url and not SAFE_URL.fullmatch(url):
        raise ValueError(f'올바르지 않은 URL: {url}')
    badge = str(raw.get('badgeText') or '').strip()
    if badge not in ALLOWED_BADGES:
        raise ValueError(f'올바르지 않은 상태값: {badge}')
    e = {
        'title': title,
        'run': run,
        'start': date_value(raw.get('start')),
        'end': date_value(raw.get('end')),
        'fee': str(raw.get('fee') or '참가비 확인 필요').strip(),
        'startPlace': str(raw.get('startPlace') or '장소 확인 필요').strip(),
        'officialLink': url,
        'badgeText': badge,
        'source': str(raw.get('source') or provenance).strip(),
        'registrationUrl': str(raw.get('registrationUrl') or '').strip(),
        'linkType': str(raw.get('linkType') or '').strip(),
        'verifiedAt': str(raw.get('verifiedAt') or '').strip(),
        'registrationStatus': str(raw.get('registrationStatus') or '').strip(),
        'statusVerifiedAt': str(raw.get('statusVerifiedAt') or '').strip(),
        'statusSourceUrl': str(raw.get('statusSourceUrl') or '').strip(),
    }
    if e['registrationStatus'] not in ALLOWED_STATUS:
        raise ValueError(f'올바르지 않은 접수검증 상태: {e["registrationStatus"]!r}')
    for k in ('registrationUrl', 'statusSourceUrl'):
        if e[k] and not SAFE_URL.fullmatch(e[k]):
            raise ValueError(f'올바르지 않은 URL: {e[k]}')
    if e['start'] and e['end'] and e['start'] > e['end']:
        raise ValueError(f'접수 시작일이 마감일보다 늦음: {title}')
    # 과거 임시값 1월 1일~대회일을 실제 접수 기간으로 오인하지 않게 합니다.
    if e['start'] == run[:4]+'-01-01' and e['end'] == run:
        e['start'] = e['end'] = ''
        if e['badgeText'] == '접수중':
            e['badgeText'] = '접수정보 없음'
    return e


def merge_row(old, new):
    if not old:
        return new
    out = old.copy()
    for key in FIELDS:
        if key in ('title', 'run'):
            continue
        val = new.get(key, '')
        if val:
            out[key] = val
    # 최신 데이터에서 명시적으로 접수 상태 '접수정보 없음'이면 기존 '접수중'을 유지하지 않습니다.
    if new.get('badgeText'):
        out['badgeText'] = new['badgeText']
    return out


def merge_rows(table, rows, origin):
    for raw in rows:
        normalized = normalize(raw, origin)
        key = event_key(normalized)
        table[key] = merge_row(table.get(key), normalized)


def get_authorized_feed(spec):
    # data/source_config.json에서 authorized:true와 HTTPS 출처를 직접 지정한 경우에만 요청.
    if not spec.get('authorized', False):
        return []
    url = str(spec.get('url') or '').strip()
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('허용된 데이터 피드는 HTTPS URL이 필요합니다')
    req = Request(url, headers={'User-Agent': 'MarathonCalendarUpdater/1.0 (approved JSON feed)', 'Accept':'application/json'})
    with urlopen(req, timeout=18) as response:
        length = response.headers.get('Content-Length')
        if length and int(length) > 2_000_000:
            raise ValueError('피드 크기 제한 초과')
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('피드 크기 제한 초과')
    payload = json.loads(raw.decode('utf-8'))
    rows = payload.get('events') if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError('피드에는 events 배열이 필요합니다')
    return rows


def manual_csv_rows(path):
    if not path.exists():
        return []
    with path.open(encoding='utf-8-sig', newline='') as fp:
        reader = csv.DictReader(fp)
        result = []
        for row in reader:
            if not any(str(v or '').strip() for v in row.values()):
                continue
            if (row.get('title') or '').lstrip().startswith('#'):
                continue
            result.append(row)
    return result


def apply_status_overrides(table):
    """Manual, source-backed changes supersede old snapshots, including empty-field clearing."""
    overrides = read_json(DATA/'status_overrides.json', [])
    if not isinstance(overrides, list):
        raise ValueError('status_overrides.json은 JSON 배열이어야 합니다')
    fields = {'start','end','officialLink','registrationUrl','linkType','verifiedAt',
              'registrationStatus','statusVerifiedAt','statusSourceUrl','badgeText','source'}
    count = 0
    for override in overrides:
        if not isinstance(override, dict):
            raise ValueError('접수 상태 수동 보정은 객체여야 합니다')
        key = event_key({'run':date_value(override.get('run')), 'title':str(override.get('title') or '')})
        if key not in table:
            raise ValueError(f'수동 보정할 대회가 기존 목록에 없음: {key}')
        for field in fields.intersection(override):
            val = str(override[field] or '').strip()
            if field in ('start', 'end'): val = date_value(val)
            if field in ('officialLink','registrationUrl','statusSourceUrl') and val and not SAFE_URL.fullmatch(val):
                raise ValueError(f'수동 보정 URL 오류: {field}={val}')
            if field == 'registrationStatus' and val not in ALLOWED_STATUS:
                raise ValueError(f'수동 보정 상태 오류: {val}')
            table[key][field] = val
        count += 1
    return count


def final_status(e, today):
    """Never infer 'open' from dates, a landing page, or an old text badge."""
    if e['run'] < today:
        return 'closed'
    if e.get('badgeText') in ('취소',):
        return 'cancelled'
    if e.get('registrationStatus') in ('closed','cancelled'):
        return e['registrationStatus']
    if e.get('end') and e['end'] < today:
        return 'closed'
    # A newer source-backed reopening notice supersedes a stale legacy closed badge.
    # Only recent, source-backed confirmation may display 'open'.
    if e.get('registrationStatus') == 'open' and e.get('statusVerifiedAt') and e.get('statusSourceUrl') and (e.get('registrationUrl') or e.get('officialLink')):
        try:
            stamp = e['statusVerifiedAt'].replace('Z','+00:00')
            checked = datetime.fromisoformat(stamp)
            if checked.tzinfo is None: checked = checked.replace(tzinfo=timezone.utc)
            hours = (datetime.now(timezone.utc) - checked.astimezone(timezone.utc)).total_seconds()/3600
            if 0 <= hours <= 24: return 'open'
        except ValueError:
            pass
    if e.get('badgeText') == '접수마감':
        return 'closed'
    if e.get('start') and e['start'] > today:
        return 'upcoming'
    return 'unknown'

def main():
    data = read_json(DATA/'base_events.json', [])
    if not isinstance(data, list) or len(data) < 1:
        raise SystemExit('초기 대회 자료가 없습니다. 이전 파일을 보존합니다.')
    table = {}
    merge_rows(table, data, '기본 대회 자료')
    # 이전에 정상 발표한 데이터는 자동 수집 실패 시에도 유지합니다.
    # 재수집분과 수동 수정분은 이 이전 데이터보다 우선합니다.
    old = read_json(DOCS/'events.json', {})
    old_events = old.get('events', []) if isinstance(old, dict) else []
    if old_events:
        merge_rows(table, old_events, '최종 정상 게시본')
    cfg = read_json(DATA/'source_config.json', {'feeds':[]})
    stats = {'base_rows':len(data), 'manual_rows':0, 'feed_rows':0, 'feed_success':0, 'feed_failures':[]}
    for spec in cfg.get('feeds', []):
        if not spec.get('authorized'):
            continue
        try:
            rows = get_authorized_feed(spec)
            # For source errors, never erase the last known events.
            merge_rows(table, rows, '승인된 데이터 출처')
            stats['feed_rows'] += len(rows)
            stats['feed_success'] += 1
        except Exception as e:
            label = str(spec.get('name') or spec.get('url') or '이름 없음')
            stats['feed_failures'].append(f'{label}: {type(e).__name__}: {e}')
    manual = manual_csv_rows(DATA/'manual_events.csv')
    # Manual, human-verified values have final precedence.
    merge_rows(table, manual, '직접 확인한 정보')
    stats['manual_rows'] = len(manual)
    stats['status_override_rows'] = apply_status_overrides(table)
    events = sorted(table.values(), key=lambda e:(e['run'],e['title']))
    if old_events and len(events) < max(1, round(len(old_events)*0.85)):
        raise SystemExit(f'보호 중단: {len(old_events)} → {len(events)} 대회 급감. 기존 데이터 보존.')
    if len(events) < len(data)*0.85:
        raise SystemExit('보호 중단: 초기 스냅샷 대비 항목이 과도하게 줄었습니다.')
    # Original '접수중' is an unverified legacy label. Remove it from the published data.
    today = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9))).date().isoformat()
    for e in events:
        e['registrationStatus'] = final_status(e, today)
        if e.get('badgeText') == '접수중':
            e['badgeText'] = '접수정보 없음'
    future = [e for e in events if e['run'] >= today]
    stats.update({
        'verified_open_count':sum(e['registrationStatus']=='open' for e in future),
        'need_verification_count':sum(e['registrationStatus']=='unknown' for e in future),
        'date_window_count':sum(bool(e.get('start') and e.get('end') and e['start']<=today<=e['end']) for e in future),
        'data_source_feed_enabled':any(spec.get('authorized') for spec in cfg.get('feeds',[])),
        'not_live_status_monitoring':True,
    })
    DOCS.mkdir(exist_ok=True)
    payload = {
        'schemaVersion': 1,
        'updatedAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'sourceNote': '이 파일의 갱신시각은 파일 게시시각입니다. 공식 실시간 접수 검증과 다릅니다. 접수중은 24시간 내 출처 확인 대회만 표시합니다.',
        'sourceHealth': { 'approvedFeedCount':stats['feed_success'], 'liveOfficialMonitoringEnabled':False, 'verifiedOpenCount':stats['verified_open_count'], 'unverifiedCount':stats['need_verification_count'] },
        'events':events,
    }
    (DOCS/'events.json').write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    (DOCS/'update-status.json').write_text(json.dumps({**stats,'checkedAt':payload['updatedAt'],'event_count':len(events)}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"OK: 대회 {len(events)}개, 최근 공식 확인 접수중 {stats['verified_open_count']}개, 접수 검증 필요 {stats['need_verification_count']}개, 피드 성공 {stats['feed_success']}개")
    for problem in stats['feed_failures']:
        print('경고:',problem)
    if stats['feed_failures'] and cfg.get('fail_on_feed_error'):
        raise SystemExit('승인된 피드 오류가 발생했습니다. 기존 정상 데이터로 공개 유지 필요.')


if __name__ == '__main__':
    main()
