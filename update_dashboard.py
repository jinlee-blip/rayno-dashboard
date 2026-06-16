"""
update_dashboard.py — Rayno Dashboard Auto-Updater
Finale Inventory API에서 데이터를 가져와 dashboard_report.html을 업데이트합니다

사용법:
  python update_dashboard.py          # 기본: Daily + Weekly + Monthly 업데이트
  python update_dashboard.py --full   # 전체: Quarterly + Yearly도 포함

최초 실행 시 Finale 로그인 정보를 입력하면 .env 파일에 저장됩니다.
"""
import os, json, re, sys
from datetime import date, datetime, timedelta

# ── 패키지 자동 설치 ────────────────────────────────────────────────────────
def install(pkg):
    os.system(f'{sys.executable} -m pip install {pkg} -q')

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError:
    install('requests'); import requests; from requests.auth import HTTPBasicAuth

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    install('python-dotenv'); from dotenv import load_dotenv; load_dotenv()

# ── 설정 ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
HTML_FILE    = os.path.join(SCRIPT_DIR, 'dashboard_report.html')
ENV_FILE     = os.path.join(SCRIPT_DIR, '.env')
FINALE_BASE  = "https://app.finaleinventory.com/raynowindowfilm/sc2/api"

MAIN_REPS = ['Pedro Mena','Miguel Carbajal','Dave Wojo','Richard Cicchino',
             'Christopher Varela','Ben Todd','Andrew Rose']

REP_NORM = {
    'Pedro Mena':'Pedro Mena','Pedro Mena ':'Pedro Mena',
    'Miguel Carbajal':'Miguel Carbajal','Miguel Carbajal ':'Miguel Carbajal',
    'Dave Wojo':'Dave Wojo','Dave Wojo ':'Dave Wojo',
    'Richard Cicchino':'Richard Cicchino','Richard Cicchino ':'Richard Cicchino',
    'Richard cicchino':'Richard Cicchino',
    'Christopher Varela':'Christopher Varela','Christopher Varela ':'Christopher Varela',
    'Christohper Varela':'Christopher Varela',
    'Ben Todd':'Ben Todd','Ben Todd ':'Ben Todd','Ben todd':'Ben Todd',
    'Andrew Rose':'Andrew Rose','Andrew Rose ':'Andrew Rose',
}

# Goals (연간 목표 — 수동 수정)
GOALS = {
    'daily':     {'Pedro Mena':21289.83,'Christopher Varela':7371.00,'Miguel Carbajal':16000.00,
                  'Ben Todd':0.00,'Dave Wojo':7659.58,'Andrew Rose':5400.00,'Richard Cicchino':5850.80,'Others':0.00},
    'weekly':    {'Pedro Mena':106449.15,'Miguel Carbajal':80000.00,'Christopher Varela':36855.00,
                  'Dave Wojo':38297.90,'Ben Todd':0.00,'Andrew Rose':27000.00,'Richard Cicchino':29254.00,'Others':0.00},
    'monthly':   {'Pedro Mena':402349.00,'Miguel Carbajal':310000.00,'Christopher Varela':136000.00,
                  'Ben Todd':136000.00,'Dave Wojo':143500.00,'Andrew Rose':100650.00,'Richard Cicchino':118000.00,'Others':0.00},
    'quarterly': {'Pedro Mena':1000665.00,'Miguel Carbajal':868859.00,'Christopher Varela':521100.00,
                  'Ben Todd':411285.00,'Dave Wojo':388524.00,'Andrew Rose':318240.00,'Richard Cicchino':420527.00,'Others':0.00},
    'yearly':    {'Pedro Mena':3335550.00,'Miguel Carbajal':2896196.00,'Christopher Varela':1737000.00,
                  'Ben Todd':1370950.00,'Dave Wojo':1295080.00,'Andrew Rose':1060800.00,'Richard Cicchino':1401757.00,'Others':0.00},
}

# ── 인증 ────────────────────────────────────────────────────────────────────
def get_creds():
    u = os.environ.get('FINALE_USER','').strip()
    p = os.environ.get('FINALE_PASS','').strip()
    if not u or not p:
        print('\n🔐 Finale Inventory 로그인 정보 입력 (최초 1회만):')
        u = input('  Username (email): ').strip()
        p = input('  Password: ').strip()
        with open(ENV_FILE, 'w') as f:
            f.write(f'FINALE_USER={u}\nFINALE_PASS={p}\n')
        os.environ['FINALE_USER'] = u
        os.environ['FINALE_PASS'] = p
        print('  ✅ .env에 저장 완료\n')
    return u, p

# ── Finale API ───────────────────────────────────────────────────────────────
def fetch_orders(u, p, start_date, end_date, label=''):
    """Finale API에서 날짜 범위의 주문을 가져옵니다."""
    out, offset, limit = [], 0, 200
    auth = HTTPBasicAuth(u, p)
    print(f'  Fetching {label or start_date+"~"+end_date}...', end=' ', flush=True)
    while True:
        try:
            r = requests.get(
                f"{FINALE_BASE}/sale",
                params={'order_date_min': start_date, 'order_date_max': end_date,
                        'limit': limit, 'offset': offset},
                auth=auth, timeout=60
            )
        except Exception as e:
            print(f'\n  ⚠️  연결 오류: {e}')
            return []
        if r.status_code == 401:
            print('\n  ❌ 로그인 실패. .env 파일 확인 후 재실행하세요.')
            sys.exit(1)
        if r.status_code != 200:
            print(f'\n  ⚠️  API 오류 {r.status_code}')
            break
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    print(f'{len(out)} orders ✓')
    return out

def norm_rep(raw):
    s = str(raw or '').strip()
    return REP_NORM.get(s, REP_NORM.get(s + ' ', s if s else 'Others'))

def to_float(v):
    try: return float(v or 0)
    except: return 0.0

def get_sub(s):
    return to_float(s.get('subtotal') or s.get('sub_total') or s.get('amount') or 0)

def get_rep(s):
    return norm_rep(s.get('sales_representative_name') or s.get('sales_representative') or s.get('rep_name') or '')

def get_customer(s):
    return str(s.get('customer_name') or s.get('customer') or 'Unknown').strip()

def is_new(s):
    return bool(s.get('new_customer'))

# ── Date ranges ──────────────────────────────────────────────────────────────
def today_str():        return date.today().strftime('%Y-%m-%d')
def week_start_str():   return (date.today() - timedelta(days=date.today().weekday())).strftime('%Y-%m-%d')
def month_start_str():  return date.today().replace(day=1).strftime('%Y-%m-%d')
def quarter_start_str():
    m = ((date.today().month - 1) // 3) * 3 + 1
    return date.today().replace(month=m, day=1).strftime('%Y-%m-%d')
def year_start_str():   return date.today().replace(month=1, day=1).strftime('%Y-%m-%d')

# ── Tier lookup ──────────────────────────────────────────────────────────────
def build_tier_map(html):
    """기존 HTML에서 customer→tier 맵을 추출합니다."""
    tier_map = {}
    for m in re.finditer(r'"([A-EO]): ([^"]+)"', html):
        tier_map[m.group(2).strip()] = m.group(1)
    for m in re.finditer(r"tier:\s*'([A-EO])'[^}]*?name:\s*'([^']+)'", html):
        tier_map[m.group(2).strip()] = m.group(1)
    return tier_map

def get_tier(name, tier_map):
    return tier_map.get(name.strip(), 'A')

# ── Build JS arrays ──────────────────────────────────────────────────────────
def build_customers_daily(orders, tier_map):
    """CUSTOMERS_DAILY 형식으로 변환합니다."""
    lines = []
    # Sort: by rep, then by amount desc
    sorted_orders = sorted(orders, key=lambda s: (get_rep(s), -get_sub(s)))
    for s in sorted_orders:
        rep = get_rep(s)
        cust = get_customer(s)
        amount = round(get_sub(s), 2)
        tier = get_tier(cust, tier_map)
        new_c = str(is_new(s)).lower()
        cust_escaped = cust.replace("'", "\\'")
        rep_escaped = rep.replace("'", "\\'")
        lines.append(f"  {{tier:'{tier}', name:'{cust_escaped}', rep:'{rep_escaped}', amount:{amount}, isNew:{new_c}}}")
    return '[\n' + ',\n'.join(lines) + '\n]'

def build_customers_period(orders, tier_map):
    """CUSTOMERS_WEEKLY / _MONTHLY_DATA 등의 형식으로 변환 (고객별 집계)."""
    cm = {}
    for s in orders:
        rep = get_rep(s)
        cust = get_customer(s)
        sub = get_sub(s)
        oid = str(s.get('sale_id') or s.get('id') or '')
        new_c = is_new(s)
        if cust not in cm:
            cm[cust] = {'revenue': 0.0, 'orders': set(), 'rep': rep, 'new_customer': new_c}
        cm[cust]['revenue'] += sub
        cm[cust]['orders'].add(oid)

    sorted_cust = sorted(cm.items(), key=lambda x: -x[1]['revenue'])
    lines = []
    for name, d in sorted_cust:
        tier = get_tier(name, tier_map)
        display_name = f'{tier}: {name}'
        rev = round(d['revenue'], 2)
        ords = len(d['orders'])
        rep = d['rep'].replace("'", "\\'")
        nc = str(d['new_customer']).lower()
        display_name_esc = display_name.replace('"', '\\"')
        lines.append(f'  {{"name":"{display_name_esc}","revenue":{rev},"orders":{ords},"rep":"{rep}","new_customer":{nc}}}')
    return '[\n' + ',\n'.join(lines) + '\n]'

def build_data_period(orders, period):
    """DATA[period] 배열 (rep별 집계, goal 포함)."""
    rm = {r: {'orders': 0, 'amount': 0.0} for r in MAIN_REPS}
    rm['Others'] = {'orders': 0, 'amount': 0.0}
    for s in orders:
        rep = get_rep(s)
        key = rep if rep in MAIN_REPS else 'Others'
        rm[key]['orders'] += 1
        rm[key]['amount'] += get_sub(s)

    goals_p = GOALS.get(period, {})
    rows = []
    # Sort by amount desc, Others last
    for rep in MAIN_REPS + ['Others']:
        d = rm[rep]
        goal = goals_p.get(rep, 0.0)
        rows.append(f"  {{ name: '{rep}', orders: {d['orders']}, amount: {round(d['amount'],2)}, goal: {goal} }}")
    return '[\n' + ',\n'.join(rows) + '\n  ]'

def build_period_totals(periods_data):
    """PERIOD_TOTALS 상수를 빌드합니다."""
    lines = []
    for period, orders in periods_data.items():
        total = round(sum(get_sub(s) for s in orders), 2)
        count = len(orders)
        lines.append(f'  {period:<10}: {{ orders: {count:5}, revenue: {total:12.2f} }}')
    return '{\n' + ',\n'.join(lines) + '\n}'

# ── HTML injection ────────────────────────────────────────────────────────────
def replace_const(html, var_name, new_val_str):
    """HTML 안의 const VAR = [...]; 또는 const VAR = {...}; 를 교체합니다."""
    m = re.search(rf'const\s+{re.escape(var_name)}\s*=\s*', html)
    if not m:
        print(f'  ⚠️  {var_name} 를 찾지 못했습니다')
        return html
    val_start = m.end()
    opener = html[val_start]
    closer = ']' if opener == '[' else '}'
    depth, i = 0, val_start
    while i < len(html):
        if html[i] == opener:   depth += 1
        elif html[i] == closer: depth -= 1
        if depth == 0: break
        i += 1
    end = i + 1
    while end < len(html) and html[end] in ' \t\n\r':
        end += 1
    if end < len(html) and html[end] == ';':
        end += 1
    return html[:m.start()] + f'const {var_name} = {new_val_str};' + html[end:]

def replace_data_period(html, period, new_val_str):
    """DATA.period = [...]; 를 교체합니다 (quarterly / yearly)."""
    m = re.search(rf'DATA\.{re.escape(period)}\s*=\s*\[', html)
    if not m:
        return html
    start = m.start()
    val_start = m.end() - 1  # '[' 포함
    depth, i = 0, val_start
    while i < len(html):
        if html[i] == '[':  depth += 1
        elif html[i] == ']': depth -= 1
        if depth == 0: break
        i += 1
    end = i + 1
    if end < len(html) and html[end] == ';':
        end += 1
    return html[:start] + f'DATA.{period} = {new_val_str};' + html[end:]

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    full_update = '--full' in sys.argv

    print()
    print('=' * 55)
    print('  Rayno Dashboard Updater')
    print(f'  날짜: {today_str()}  |  모드: {"전체(--full)" if full_update else "기본"}')
    print('=' * 55)

    u, p = get_creds()

    # Finale API 연결 테스트
    test = requests.get(f"{FINALE_BASE}/sale?limit=1", auth=HTTPBasicAuth(u, p), timeout=15)
    if test.status_code == 401:
        print('\n❌ Finale 로그인 실패. .env 파일을 삭제하고 재실행하세요.')
        return
    print(f'  Finale API 연결 ✅\n')

    # 기존 HTML 읽기
    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        html = f.read()
    tier_map = build_tier_map(html)
    print(f'  Tier 맵: {len(tier_map)}개 고객 확인\n')

    # ── 데이터 수집 ──────────────────────────────────────────────────────────
    print('📡 Finale에서 데이터 수집 중...')
    today     = today_str()
    wk_start  = week_start_str()
    mo_start  = month_start_str()
    qt_start  = quarter_start_str()
    yr_start  = year_start_str()

    daily_orders   = fetch_orders(u, p, today,    today,    'Today')
    weekly_orders  = fetch_orders(u, p, wk_start, today,    'This Week')
    monthly_orders = fetch_orders(u, p, mo_start, today,    'This Month')

    if full_update:
        quarterly_orders = fetch_orders(u, p, qt_start, today, 'This Quarter')
        yearly_orders    = fetch_orders(u, p, yr_start, today, 'This Year')
    else:
        print('  Quarterly/Yearly: PERIOD_TOTALS만 업데이트합니다.')
        print('  (전체 업데이트 시 --full 옵션 사용)')
        quarterly_orders = fetch_orders(u, p, qt_start, today, 'Quarter (totals)')
        yearly_orders    = fetch_orders(u, p, yr_start, today, 'Year (totals)')

    print()
    print('📊 데이터 요약:')
    for label, orders in [('Daily', daily_orders), ('Weekly', weekly_orders),
                           ('Monthly', monthly_orders), ('Quarterly', quarterly_orders),
                           ('Yearly', yearly_orders)]:
        total = sum(get_sub(s) for s in orders)
        print(f'  {label:<12}: {len(orders):5} orders  ${total:>12,.2f}')

    # ── HTML 업데이트 ─────────────────────────────────────────────────────────
    print('\n✏️  dashboard_report.html 업데이트 중...')

    # 1. PERIOD_TOTALS
    pt_data = {'daily': daily_orders, 'weekly': weekly_orders, 'monthly': monthly_orders,
               'quarterly': quarterly_orders, 'yearly': yearly_orders}
    html = replace_const(html, 'PERIOD_TOTALS', build_period_totals(pt_data))
    print('  ✅ PERIOD_TOTALS')

    # 2. CUSTOMERS_DAILY
    html = replace_const(html, 'CUSTOMERS_DAILY', build_customers_daily(daily_orders, tier_map))
    print('  ✅ CUSTOMERS_DAILY')

    # 3. CUSTOMERS_WEEKLY
    html = replace_const(html, 'CUSTOMERS_WEEKLY', build_customers_period(weekly_orders, tier_map))
    print('  ✅ CUSTOMERS_WEEKLY')

    # 4. DATA.daily (rep 별 일일 실적)
    html = replace_const(html, 'CUSTOMERS_DAILY', build_customers_daily(daily_orders, tier_map))

    # DATA arrays — find DATA object and patch individual period arrays
    # Build DATA.daily
    daily_data_str = build_data_period(daily_orders, 'daily')
    # Replace the daily: [...] inside DATA object
    html = re.sub(
        r'(daily:\s*)\[[\s\S]*?\](\s*,)',
        lambda m: m.group(1) + daily_data_str.strip() + m.group(2),
        html, count=1
    )
    print('  ✅ DATA.daily')

    # DATA.weekly
    weekly_data_str = build_data_period(weekly_orders, 'weekly')
    html = replace_data_period(html, 'weekly', weekly_data_str)
    print('  ✅ DATA.weekly')

    # DATA.monthly
    monthly_data_str = build_data_period(monthly_orders, 'monthly')
    html = re.sub(
        r'(monthly:\s*)\[[\s\S]*?\](\s*,)',
        lambda m: m.group(1) + monthly_data_str.strip() + m.group(2),
        html, count=1
    )
    print('  ✅ DATA.monthly')

    # _MONTHLY_DATA (customer table for monthly)
    html = replace_const(html, '_MONTHLY_DATA', build_customers_period(monthly_orders, tier_map))
    print('  ✅ _MONTHLY_DATA')

    # Full update: rebuild quarterly + yearly customer arrays too
    if full_update:
        quarterly_data_str = build_data_period(quarterly_orders, 'quarterly')
        html = replace_data_period(html, 'quarterly', quarterly_data_str)
        html = replace_const(html, '_QUARTERLY_DATA', build_customers_period(quarterly_orders, tier_map))
        print('  ✅ DATA.quarterly + _QUARTERLY_DATA')

        yearly_data_str = build_data_period(yearly_orders, 'yearly')
        html = replace_data_period(html, 'yearly', yearly_data_str)
        html = replace_const(html, '_YEARLY_DATA', build_customers_period(yearly_orders, tier_map))
        print('  ✅ DATA.yearly + _YEARLY_DATA')

    # 저장
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

    print()
    print('=' * 55)
    print('  ✅ 업데이트 완료!')
    print(f'  파일: {HTML_FILE}')
    d_total = sum(get_sub(s) for s in daily_orders)
    m_total = sum(get_sub(s) for s in monthly_orders)
    print(f'  Today : {len(daily_orders)} orders  ${d_total:,.2f}')
    print(f'  Month : {len(monthly_orders)} orders  ${m_total:,.2f}')
    print('=' * 55)
    print()

if __name__ == '__main__':
    main()
