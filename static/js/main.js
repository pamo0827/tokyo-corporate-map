const map = L.map('map', {
    zoomControl: false
}).setView([35.6861, 139.7537], 14);

L.control.zoom({
    position: 'bottomright'
}).addTo(map);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

const companyList = document.getElementById('company-list');
const searchInput = document.getElementById('search-input');
const detailPanel = document.getElementById('detail-panel');
const detailContent = document.getElementById('detail-content');
const viewToggle = document.getElementById('view-toggle');

let currentCompany = null;   // 最後に選択した企業
let currentView = 'detail';  // 'map' | 'detail'（初期は詳細）
let detailReqId = 0;         // 詳細取得の競合防止

let allCompaniesData = [];
let markers = {};

const defaultIcon = new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34]
});

function addCompanyMarker(company) {
    const marker = L.marker([company.latitude, company.longitude], { icon: defaultIcon }).addTo(map);
    markers[company.id] = marker;
    marker.bindPopup(`<b>${company.name}</b>`);
}

fetch('/api/companies')
    .then(response => response.json())
    .then(companies => {
        allCompaniesData = companies;
        // ピンは初期表示せず、企業選択時に「その企業＋周辺」を表示する
        renderCompanyList(allCompaniesData);
    })
    .catch(error => console.error('Error fetching companies:', error));

// 住所から所在地（区・市など）を抽出する
function extractWard(address) {
    if (!address) return '';
    let a = address
        .replace(/^日本[、,]?\s*/, '')
        .replace(/〒?\s*\d{3}-?\d{4}\s*/, '')
        .replace(/東京都/, '');
    const m = a.match(/^(.+?[区市町村])/);
    if (m) {
        return m[1];
    }
    return 'その他';
}

// 1行＝企業名＋所在地 の行要素を作成
function createCompanyRow(company) {
    const div = document.createElement('div');
    div.className = 'search-result-item';
    div.dataset.id = company.id;

    const nameSpan = document.createElement('span');
    nameSpan.className = 'search-result-name';
    nameSpan.textContent = company.name;

    div.appendChild(nameSpan);
    div.title = company.address || '';

    div.addEventListener('click', () => selectCompany(company, div));
    return div;
}

// 五十音ソート用キー（法人格の語を除いて並べる）
function nameSortKey(name) {
    return (name || '')
        .replace(/(株式会社|有限会社|合同会社|（株）|\(株\)|㈱)/g, '')
        .trim();
}

// 「あかさたな」分類（先頭文字の五十音行を判定）
const GOJUON_ORDER = ['あ', 'か', 'さ', 'た', 'な', 'は', 'ま', 'や', 'ら', 'わ', '英数', '漢字・その他'];

function gojuonRow(name) {
    const key = nameSortKey(name);
    if (!key) return '漢字・その他';
    const ch = key[0];
    let c = ch.codePointAt(0);
    if (c >= 0x30A1 && c <= 0x30F6) c -= 0x60;   // カタカナ→ひらがな
    if (c >= 0x3041 && c <= 0x304A) return 'あ';
    if (c >= 0x304B && c <= 0x3054) return 'か';
    if (c >= 0x3055 && c <= 0x305E) return 'さ';
    if (c >= 0x305F && c <= 0x306E) return 'た';
    if (c >= 0x306F && c <= 0x3073) return 'な';
    if (c >= 0x3074 && c <= 0x307D) return 'は';
    if (c >= 0x307E && c <= 0x3082) return 'ま';
    if (c >= 0x3083 && c <= 0x3088) return 'や';
    if (c >= 0x3089 && c <= 0x308D) return 'ら';
    if (c >= 0x308E && c <= 0x3093) return 'わ';
    if ((ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') ||
        (c >= 0xFF21 && c <= 0xFF3A) || (c >= 0xFF41 && c <= 0xFF5A) ||
        (ch >= '0' && ch <= '9') || (c >= 0xFF10 && c <= 0xFF19)) return '英数';
    return '漢字・その他';
}

// 「あかさたな」分類の折りたたみセクションで表示（初期は閉じる）
function renderCompanyList(companies, openAll) {
    companyList.innerHTML = '';
    if (!companies || companies.length === 0) {
        companyList.innerHTML = '<div class="list-empty">企業がありません。</div>';
        return;
    }

    const groups = {};
    companies.forEach(c => {
        const row = gojuonRow(c.name);
        (groups[row] = groups[row] || []).push(c);
    });

    GOJUON_ORDER.forEach(row => {
        const list = groups[row];
        if (!list || list.length === 0) return;

        const group = document.createElement('div');
        group.className = 'kana-group' + (openAll ? ' open' : '');

        const header = document.createElement('div');
        header.className = 'kana-header';
        header.innerHTML = `<span class="kana-arrow">▶</span>` +
            `<span class="kana-label">${escapeHtml(row)}</span>` +
            `<span class="kana-count">${list.length}</span>`;
        header.addEventListener('click', () => group.classList.toggle('open'));
        group.appendChild(header);

        const body = document.createElement('div');
        body.className = 'kana-body';
        list.sort((a, b) => nameSortKey(a.name).localeCompare(nameSortKey(b.name), 'ja'))
            .forEach(c => body.appendChild(createCompanyRow(c)));
        group.appendChild(body);

        companyList.appendChild(group);
    });
}

// 全ピンを消す
function clearMarkers() {
    Object.values(markers).forEach(m => map.removeLayer(m));
    markers = {};
}

// 住所→座標（geolonia経由）。idを渡すとDBにも保存される。
function geocodeAddress(address, id) {
    const idq = id != null ? `&id=${encodeURIComponent(id)}` : '';
    return fetch(`/api/geocode?address=${encodeURIComponent(address)}${idq}`)
        .then(r => r.json())
        .then(d => (d && d.lat != null) ? [d.lat, d.lng] : null)
        .catch(() => null);
}

// 企業の座標を解決（無ければ住所→EDINET本社住所の順でジオコーディング）
function resolveCoords(company) {
    if (company.latitude != null && company.longitude != null) {
        return Promise.resolve([company.latitude, company.longitude]);
    }
    if (company.address) {
        return geocodeAddress(company.address, company.id);
    }
    if (company.edinet_code) {
        return fetch(`/api/edinet_detail?code=${encodeURIComponent(company.edinet_code)}`)
            .then(r => r.json())
            .then(d => {
                const addr = d && d.data && d.data.hq_address;
                return addr ? geocodeAddress(addr, company.id) : null;
            })
            .catch(() => null);
    }
    return Promise.resolve(null);
}

// 企業を選択 → 座標を解決して、その企業のピンだけ表示
function selectCompany(company, rowEl) {
    currentCompany = company;

    document.querySelectorAll('.search-result-item.selected')
        .forEach(el => el.classList.remove('selected'));
    if (rowEl) rowEl.classList.add('selected');

    resolveCoords(company).then(coords => {
        if (currentCompany !== company || !coords) return;
        company.latitude = coords[0];
        company.longitude = coords[1];
        clearMarkers();
        addCompanyMarker(company);
        map.setView(coords, 16);
        if (markers[company.id]) markers[company.id].openPopup();
    });

    if (currentView === 'detail') {
        openCompanyDetail(company);
    }
}

// 右ペインの表示切り替え（地図 / 詳細）
function setView(view) {
    currentView = view;
    viewToggle.querySelectorAll('button').forEach(b => {
        b.classList.toggle('active', b.dataset.view === view);
    });
    if (view === 'detail') {
        detailPanel.classList.remove('hidden');
        if (currentCompany) {
            openCompanyDetail(currentCompany);
        }
    } else {
        detailPanel.classList.add('hidden');
        map.invalidateSize();
    }
}

viewToggle.addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-view]');
    if (btn) setView(btn.dataset.view);
});

// 一覧で選んだ企業の詳細を開く → 右側に EDINET と gBizINFO の両方を表示
function openCompanyDetail(company) {
    const reqId = ++detailReqId;
    detailContent.innerHTML =
        `<div class="detail-name">${escapeHtml(company.name)}</div>` +
        `<section id="d-edinet" class="dual-sec"></section>` +
        `<section id="d-gbiz" class="dual-sec"></section>`;
    if (company.edinet_code) {
        // EDINET取得 → 法人番号が手元に無ければEDINETの法人番号でgBizINFOを取得
        fetchEdinetSection(reqId, company.edinet_code)
            .then(cn => fetchGbizSection(reqId, company.corporate_number || cn));
    } else {
        document.getElementById('d-edinet').innerHTML =
            sectionHead('EDINET DB', 'edinet') +
            '<div class="detail-empty">EDINETデータなし（非上場など）</div>';
        fetchGbizSection(reqId, company.corporate_number);
    }
}

// セクション見出し（提供元バッジ＋取得状況）
function sectionHead(label, cls, cached, remaining) {
    let meta = '';
    if (cls === 'edinet' && cached !== undefined) {
        meta = cached
            ? '<span class="detail-badge cached">キャッシュ</span>'
            : `<span class="detail-badge live">API取得${remaining != null ? `・本日残り${escapeHtml(remaining)}回` : ''}</span>`;
    }
    return `<div class="d-head"><span class="src-badge ${cls}">${escapeHtml(label)}</span>${meta}</div>`;
}

// ===== EDINET DB セクション（全フィールド）=====
function fetchEdinetSection(reqId, code) {
    if (reqId !== detailReqId) return Promise.resolve(null);
    const el = document.getElementById('d-edinet');
    el.innerHTML = sectionHead('EDINET DB', 'edinet') + '<div class="detail-loading">取得中...</div>';
    return fetch(`/api/edinet_detail?code=${encodeURIComponent(code)}`)
        .then(r => r.json().then(d => ({ ok: r.ok, d })))
        .then(({ ok, d }) => {
            if (reqId !== detailReqId) return null;
            if (!ok || d.error || !d.data) {
                el.innerHTML = sectionHead('EDINET DB', 'edinet') +
                    `<div class="detail-empty">取得できませんでした（${escapeHtml((d && d.error) || '')}）</div>`;
                return null;
            }
            el.innerHTML = sectionHead('EDINET DB', 'edinet', d.cached, d.remaining) + renderValue(d.data);
            return d.data.corporate_number || null;
        })
        .catch(() => {
            if (reqId === detailReqId) {
                el.innerHTML = sectionHead('EDINET DB', 'edinet') + '<div class="detail-empty">取得エラー</div>';
            }
            return null;
        });
}

// ===== gBizINFO セクション（全フィールド）=====
function fetchGbizSection(reqId, corporateNumber) {
    if (reqId !== detailReqId) return;
    const el = document.getElementById('d-gbiz');
    if (!el) return;
    if (!corporateNumber) {
        el.innerHTML = sectionHead('gBizINFO', 'gbiz') +
            '<div class="detail-empty">法人番号が無いため取得できません</div>';
        return;
    }
    el.innerHTML = sectionHead('gBizINFO', 'gbiz') + '<div class="detail-loading">取得中...</div>';
    fetch(`/api/company_detail?corporate_number=${encodeURIComponent(corporateNumber)}`)
        .then(r => r.json().then(d => ({ ok: r.ok, d })))
        .then(({ ok, d }) => {
            if (reqId !== detailReqId) return;
            el.innerHTML = sectionHead('gBizINFO', 'gbiz') +
                ((!ok || d.error) ? '<div class="detail-empty">取得できませんでした</div>' : renderValue(d));
        })
        .catch(() => {
            if (reqId === detailReqId) {
                el.innerHTML = sectionHead('gBizINFO', 'gbiz') + '<div class="detail-empty">取得エラー</div>';
            }
        });
}

// フィールド名の日本語ラベル（EDINET DB / gBizINFO）
const FIELD_LABELS = {
    // 基本
    name: '名称', name_ja: '名称（日本語）', name_en: '名称（英語）', kana: 'フリガナ',
    corporate_number: '法人番号', edinet_code: 'EDINETコード', sec_code: '証券コード',
    lei: 'LEIコード', industry: '業種', accounting_standard: '会計基準',
    listing_status: '上場状態', listing_status_as_of: '上場状態 基準日', is_delisted: '上場廃止',
    is_consolidated: '連結区分', is_correction: '訂正フラグ',
    founding_date: '設立日', date_of_establishment: '設立日',
    hq_address: '本社所在地', location: '所在地', postal_code: '郵便番号',
    representative_name: '代表者名', representative_position: '代表者役職',
    status: '状態', company_url: '企業URL', update_date: '更新日',
    business_summary: '事業概要', business_items: '事業項目（コード）',
    qualification_grade: '資格等級', basic_attr_confidence: '基本属性の信頼度',
    data_notes: 'データ注記', data_years: 'データ対象年', sources: '出典',
    doc_id: '書類ID', title: '書類名', pdf_url: 'PDF URL',
    edinet_filing_url: 'EDINET提出書類URL', disclosure_date: '開示日',
    submit_date: '提出日', fiscal_year: '会計年度', fiscal_year_end: '決算期末',
    latest_fiscal_year: '最新会計年度', quarter: '四半期',
    // 信用・指標
    credit_rating: '信用格付', credit_score: '信用スコア',
    roe_official: 'ROE（自己資本利益率）', equity_ratio_official: '自己資本比率',
    per: '株価収益率(PER)', eps: '1株当たり利益(EPS)', bps: '1株当たり純資産(BPS)',
    total_shareholder_return: '株主総利回り(TSR)', total_return_share_price_index: 'トータルリターン株価指数',
    // 損益
    revenue: '売上高', revenue_change: '売上高 増減率', cost_of_sales: '売上原価',
    gross_profit: '売上総利益', sga: '販売費及び一般管理費', operating_income: '営業利益',
    non_operating_income: '営業外収益', non_operating_expenses: '営業外費用',
    ordinary_income: '経常利益', profit_before_tax: '税引前利益', income_taxes: '法人税等',
    net_income: '当期純利益', depreciation: '減価償却費', rnd_expenses: '研究開発費',
    interest_expenses: '支払利息',
    // 予想
    forecast_revenue: '予想売上高', forecast_operating_income: '予想営業利益',
    forecast_ordinary_income: '予想経常利益', forecast_net_income: '予想当期純利益',
    forecast_eps: '予想EPS', forecast_dividend_per_share: '予想1株配当',
    // 財政状態
    total_assets: '総資産', current_assets: '流動資産', noncurrent_assets: '固定資産',
    cash: '現金及び預金', trade_receivables: '売上債権', inventories: '棚卸資産',
    ppe: '有形固定資産', intangible_assets: '無形固定資産', software: 'ソフトウェア',
    investment_securities: '投資有価証券', investments_and_other_assets: '投資その他の資産',
    allowance_for_doubtful_accounts: '貸倒引当金',
    total_liabilities: '負債合計', current_liabilities: '流動負債', noncurrent_liabilities: '固定負債',
    trade_payables: '仕入債務', accounts_payable_other: 'その他未払金',
    contract_liabilities: '契約負債', provision_for_bonuses: '賞与引当金',
    long_term_loans: '長期借入金', current_portion_lt_loans: '長期借入金（1年内）',
    deferred_tax_liabilities: '繰延税金負債',
    net_assets: '純資産', shareholders_equity: '株主資本', capital_surplus: '資本剰余金',
    retained_earnings: '利益剰余金', capital_stock_gbiz: '資本金（gBizINFO）', capital_stock: '資本金',
    // CF
    cf_operating: '営業キャッシュフロー', cf_investing: '投資キャッシュフロー', cf_financing: '財務キャッシュフロー',
    // 株式
    shares_issued: '発行済株式数', float_shares: '浮動株数',
    shares_section_source: '株式情報の出所',
    cross_shareholding_total_book_value: '政策保有株式 簿価合計',
    cross_shareholding_total_shares_held: '政策保有株式 銘柄数',
    treasury_shares_count: '自己株式数', treasury_end_period_holding_count: '期末自己株式数',
    treasury_shares_source: '自己株式 出所', treasury_shares_quality_flag: '自己株式 品質フラグ',
    treasury_cancelled_count: '自己株式消却 株数', treasury_cancelled_amount: '自己株式消却 金額',
    treasury_disposed_solicitation_count: '自己株式処分(募集) 株数',
    treasury_disposed_solicitation_amount: '自己株式処分(募集) 金額',
    treasury_merger_transfer_count: '自己株式(合併等) 株数', treasury_merger_transfer_amount: '自己株式(合併等) 金額',
    treasury_other_disposed_count: '自己株式その他処分 株数', treasury_other_disposed_amount: '自己株式その他処分 金額',
    trust_note_type: '信託 注記区分', trust_quality_flag: '信託 品質フラグ', trust_share_note_type: '信託株式 注記区分',
    // 人材・ガバナンス
    num_employees: '従業員数', num_employees_gbiz: '従業員数（gBizINFO）',
    num_male_employees: '男性従業員数', num_female_employees: '女性従業員数',
    temp_employees: '臨時従業員数', employee_number: '従業員数',
    company_size_male: '従業員数（男）', company_size_female: '従業員数（女）',
    avg_age: '平均年齢', avg_tenure_years: '平均勤続年数', avg_annual_salary: '平均年収',
    female_manager_ratio: '女性管理職比率', male_parental_leave_ratio: '男性育休取得率',
    gender_pay_gap_all: '男女賃金差（全体）', gender_pay_gap_regular: '男女賃金差（正社員）',
    male_directors: '男性役員数', directors_shares_held: '役員 保有株式数',
    directors_ownership_ratio: '役員 持株比率',
    director_remuneration_total: '役員報酬 総額', director_remuneration_headcount: '役員報酬 対象人数',
    // 区分
    latest_financials: '最新財務（有価証券報告書）', latest_earnings: '最新決算（決算短信）',
    number_of_activity: '活動件数',
    is_restated_eps: 'EPS遡及修正', is_restated_diluted_eps: '潜在株式調整後EPS遡及修正', is_restated_bps: 'BPS遡及修正',
    // 配当・1株指標
    dividend_per_share: '1株当たり配当', interim_dividend_per_share: '中間配当（1株）',
    yearend_dividend_per_share: '期末配当（1株）', adjusted_annual_dividend_per_share: '調整後 年間配当',
    dividends_total_announced: '配当総額（公表）', cash_dividends_paid: '配当金支払額',
    payout_ratio: '配当性向', forecast_doe: '予想DOE（株主資本配当率）',
    forecast_dividend_total: '予想配当総額', shares_eligible: '配当対象株式数',
    diluted_eps: '潜在株式調整後EPS',
    // 損益・増減率
    comprehensive_income: '包括利益', capex: '設備投資額',
    interest_income: '受取利息', effective_tax_rate: '実効税率',
    revenue_change: '売上高 増減率', operating_income_change: '営業利益 増減率',
    ordinary_income_change: '経常利益 増減率', net_income_change: '当期純利益 増減率',
    forecast_revenue_change: '予想売上高 増減率', forecast_operating_income_change: '予想営業利益 増減率',
    forecast_ordinary_income_change: '予想経常利益 増減率', forecast_net_income_change: '予想当期純利益 増減率',
    forecast_fiscal_year: '予想 会計年度',
    // 財政状態（追加）
    deferred_tax_assets: '繰延税金資産', net_defined_benefit_liability: '退職給付に係る負債',
    ibd_current: '有利子負債（流動）', ibd_noncurrent: '有利子負債（固定）',
    owners_equity: '自己資本（親会社株主持分）', non_controlling_interests: '非支配株主持分',
    treasury_stock: '自己株式', cf_exchange_effect: '現金等への為替影響額',
    // ガバナンス（追加）
    female_directors: '女性役員数', female_director_ratio: '女性役員比率',
    gender_pay_gap_nonregular: '男女賃金差（非正規）',
    // 出所・その他
    disclosure_time: '開示時刻', source_disclosure_date: '出所 開示日',
    source_quarter: '出所 四半期', value: '値',
    // 財務（追加）
    extraordinary_income: '特別利益', extraordinary_loss: '特別損失',
    impairment_loss: '減損損失', goodwill: 'のれん',
    land: '土地', construction_in_progress: '建設仮勘定',
    short_term_loans: '短期借入金', bonds_payable: '社債',
    commercial_papers: 'コマーシャルペーパー', net_defined_benefit_asset: '退職給付に係る資産',
    // 不動産
    real_estate: '不動産情報', bs_land_m_yen: '土地（百万円）',
    bs_real_estate_total_m_yen: '不動産合計（百万円）',
    // 自己株式（追加）
    treasury_shares_as_of_date: '自己株式 基準日', treasury_shares_count_kei: '自己株式数（計）',
};

function fieldLabel(k) {
    return FIELD_LABELS[k] || k;
}

// 任意のJSON値を再帰的にテーブル/リストへ（全フィールドをそのまま表示）
function renderValue(v) {
    if (v === null || v === undefined || v === '') return '<span class="muted">—</span>';
    if (typeof v === 'number') return escapeHtml(v.toLocaleString());
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (Array.isArray(v)) {
        if (v.length === 0) return '<span class="muted">（空）</span>';
        if (v.every(x => x === null || typeof x !== 'object')) {
            return escapeHtml(v.join(', '));
        }
        return v.map(item => `<div class="arr-item">${renderValue(item)}</div>`).join('');
    }
    if (typeof v === 'object') {
        const rows = Object.keys(v).map(k =>
            `<tr><th>${escapeHtml(fieldLabel(k))}</th><td>${renderValue(v[k])}</td></tr>`).join('');
        return `<table class="kv"><tbody>${rows}</tbody></table>`;
    }
    const s = String(v);
    if (/^https?:\/\//.test(s)) {
        return `<a href="${escapeHtml(s)}" target="_blank" rel="noopener">${escapeHtml(s)}</a>`;
    }
    return escapeHtml(s).replace(/\n/g, '<br>');
}

function escapeHtml(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ===== 検索（左上の1か所・ローカルDBを絞り込み）=====
searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim().toLowerCase();
    if (!q) {
        renderCompanyList(allCompaniesData, false);
        return;
    }
    const filtered = allCompaniesData.filter(c =>
        (c.name && c.name.toLowerCase().includes(q)) ||
        (c.address && c.address.toLowerCase().includes(q))
    );
    renderCompanyList(filtered, true);
});

// Mobile-specific functionality
function isMobileDevice() {
    return window.innerWidth <= 768;
}

// Touch-friendly search result handling
let touchStartTime = 0;
document.addEventListener('touchstart', (e) => {
    touchStartTime = Date.now();
});

document.addEventListener('touchend', (e) => {
    const touchDuration = Date.now() - touchStartTime;
    if (touchDuration < 300) { // Short tap
        const target = e.target.closest('.search-result-item');
        if (target) {
            target.click();
        }
    }
});

// Enhanced map interaction for mobile
if (isMobileDevice()) {
    // Disable map zoom on double tap to prevent conflicts
    map.doubleClickZoom.disable();
    
    // Re-enable double tap zoom with custom handler
    let lastTap = 0;
    map.on('click', (e) => {
        const currentTime = new Date().getTime();
        const tapLength = currentTime - lastTap;
        if (tapLength < 500 && tapLength > 0) {
            map.setZoom(map.getZoom() + 1);
            e.originalEvent.preventDefault();
        }
        lastTap = currentTime;
    });
}

// 一覧と地図の境界をドラッグしてサイズ変更
const resizer = document.getElementById('resizer');
const listPanel = document.getElementById('list-panel');
const appEl = document.getElementById('app');
let isResizing = false;

// 縦積みレイアウト（スマホ）かどうか
function isVerticalLayout() {
    return window.matchMedia('(max-width: 768px)').matches;
}

function startResize(e) {
    isResizing = true;
    resizer.classList.add('dragging');
    document.body.style.userSelect = 'none';
    document.body.style.cursor = isVerticalLayout() ? 'row-resize' : 'col-resize';
    e.preventDefault();
}

function moveResize(e) {
    if (!isResizing) return;
    const point = e.touches ? e.touches[0] : e;
    const rect = appEl.getBoundingClientRect();
    const MIN = 120;
    if (isVerticalLayout()) {
        let h = point.clientY - rect.top;
        h = Math.max(MIN, Math.min(rect.height - MIN, h));
        listPanel.style.height = h + 'px';
        listPanel.style.width = '100%';
    } else {
        let w = point.clientX - rect.left;
        w = Math.max(MIN, Math.min(rect.width - MIN, w));
        listPanel.style.width = w + 'px';
    }
    map.invalidateSize();
    if (e.cancelable) e.preventDefault();
}

function stopResize() {
    if (!isResizing) return;
    isResizing = false;
    resizer.classList.remove('dragging');
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    map.invalidateSize();
}

resizer.addEventListener('mousedown', startResize);
resizer.addEventListener('touchstart', startResize, { passive: false });
document.addEventListener('mousemove', moveResize);
document.addEventListener('touchmove', moveResize, { passive: false });
document.addEventListener('mouseup', stopResize);
document.addEventListener('touchend', stopResize);

// 画面回転やリサイズで縦横が切り替わったらインラインサイズをリセット
window.addEventListener('resize', () => {
    listPanel.style.width = '';
    listPanel.style.height = '';
    map.invalidateSize();
});

