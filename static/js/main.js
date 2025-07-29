// 東京都の境界を定義
const TOKYO_BOUNDS = {
    north: 35.9,
    south: 35.5,
    east: 139.9,
    west: 139.4
};

const map = L.map('map', {
    zoomControl: false,
    maxBounds: [[TOKYO_BOUNDS.south, TOKYO_BOUNDS.west], [TOKYO_BOUNDS.north, TOKYO_BOUNDS.east]],
    maxBoundsViscosity: 1.0
}).setView([35.6861, 139.7537], 14);

L.control.zoom({
    position: 'bottomright'
}).addTo(map);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

const searchInput = document.getElementById('search-input');
const searchResults = document.getElementById('search-results');
const searchContainer = document.getElementById('search-container');
const searchToggleBtn = document.getElementById('search-toggle-btn');
const favoritesToggleBtn = document.getElementById('favorites-toggle-btn');
const favoritesSidebar = document.getElementById('favorites-sidebar');
const favoritesList = document.getElementById('favorites-list');
const registerToggle = document.getElementById('register-toggle');
const registerForm = document.getElementById('register-form');
const toggleIcon = document.getElementById('toggle-icon');
const companyNameInput = document.getElementById('company-name');
const companyAddressInput = document.getElementById('company-address');
const companyNumberInput = document.getElementById('company-number');
const registerBtn = document.getElementById('register-btn');
const cancelBtn = document.getElementById('cancel-btn');
const registerMessage = document.getElementById('register-message');

let searchTimeout;
let allCompaniesData = [];
let markers = {};
let currentRouteLayer = null;

// 東京主要駅データ
const tokyoStations = [
    {name: "新宿駅", lat: 35.6896, lng: 139.7006, lines: ["JR山手線", "JR中央線", "小田急線", "京王線", "地下鉄丸ノ内線"]},
    {name: "渋谷駅", lat: 35.6580, lng: 139.7016, lines: ["JR山手線", "JR埼京線", "東急東横線", "地下鉄半蔵門線"]},
    {name: "池袋駅", lat: 35.7295, lng: 139.7109, lines: ["JR山手線", "JR埼京線", "東武東上線", "西武池袋線"]},
    {name: "東京駅", lat: 35.6812, lng: 139.7671, lines: ["JR東海道線", "JR中央線", "地下鉄丸ノ内線"]},
    {name: "品川駅", lat: 35.6284, lng: 139.7387, lines: ["JR東海道線", "JR山手線", "京急本線"]},
    {name: "上野駅", lat: 35.7133, lng: 139.7775, lines: ["JR山手線", "JR東北線", "地下鉄銀座線"]},
    {name: "秋葉原駅", lat: 35.6984, lng: 139.7731, lines: ["JR山手線", "JR京浜東北線", "地下鉄日比谷線"]},
    {name: "有楽町駅", lat: 35.6751, lng: 139.7640, lines: ["JR山手線", "JR京浜東北線"]},
    {name: "新橋駅", lat: 35.6658, lng: 139.7587, lines: ["JR東海道線", "JR山手線", "地下鉄銀座線"]},
    {name: "大手町駅", lat: 35.6847, lng: 139.7642, lines: ["地下鉄丸ノ内線", "地下鉄東西線", "地下鉄千代田線"]},
    {name: "六本木駅", lat: 35.6627, lng: 139.7314, lines: ["地下鉄日比谷線", "地下鉄大江戸線"]},
    {name: "恵比寿駅", lat: 35.6465, lng: 139.7100, lines: ["JR山手線", "JR埼京線", "地下鉄日比谷線"]},
    {name: "目黒駅", lat: 35.6333, lng: 139.7156, lines: ["JR山手線", "東急目黒線", "地下鉄南北線"]},
    {name: "五反田駅", lat: 35.6259, lng: 139.7238, lines: ["JR山手線", "東急池上線"]},
    {name: "大崎駅", lat: 35.6197, lng: 139.7289, lines: ["JR山手線", "JR埼京線", "りんかい線"]},
    {name: "田町駅", lat: 35.6456, lng: 139.7478, lines: ["JR山手線", "JR京浜東北線"]},
    {name: "浜松町駅", lat: 35.6556, lng: 139.7570, lines: ["JR山手線", "JR京浜東北線", "東京モノレール"]},
    {name: "神田駅", lat: 35.6916, lng: 139.7708, lines: ["JR山手線", "JR中央線", "地下鉄銀座線"]},
    {name: "御茶ノ水駅", lat: 35.6993, lng: 139.7649, lines: ["JR中央線", "地下鉄丸ノ内線", "地下鉄千代田線"]},
    {name: "水道橋駅", lat: 35.7022, lng: 139.7528, lines: ["JR中央線", "地下鉄三田線"]},
    {name: "飯田橋駅", lat: 35.7026, lng: 139.7447, lines: ["JR中央線", "地下鉄東西線", "地下鉄南北線"]},
    {name: "市ヶ谷駅", lat: 35.6938, lng: 139.7383, lines: ["JR中央線", "地下鉄南北線", "地下鉄有楽町線"]},
    {name: "四ツ谷駅", lat: 35.6869, lng: 139.7307, lines: ["JR中央線", "地下鉄丸ノ内線", "地下鉄南北線"]},
    {name: "信濃町駅", lat: 35.6794, lng: 139.7199, lines: ["JR中央線"]},
    {name: "代々木駅", lat: 35.6833, lng: 139.7022, lines: ["JR山手線", "JR中央線", "地下鉄大江戸線"]}
];

const favoriteIcon = new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

const defaultIcon = new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

function getFavorites() {
    const favorites = localStorage.getItem('favoriteCompanies');
    return favorites ? JSON.parse(favorites) : {};
}

function saveFavorites(favorites) {
    localStorage.setItem('favoriteCompanies', JSON.stringify(favorites));
}

function renderFavoritesList() {
    const favorites = getFavorites();
    favoritesList.innerHTML = '';
    if (Object.keys(favorites).length === 0) {
        favoritesList.innerHTML = '<li style="padding: 10px;">お気に入りの企業はありません。</li>';
        return;
    }
    for (const id in favorites) {
        const company = favorites[id];
        const li = document.createElement('li');
        li.textContent = company.name;
        li.dataset.id = id;
        li.dataset.latitude = company.latitude;
        li.dataset.longitude = company.longitude;
        li.addEventListener('click', () => {
            map.setView([company.latitude, company.longitude], 15);
            if (markers[id]) {
                markers[id].openPopup();
            }
            favoritesSidebar.classList.remove('open');
        });
        favoritesList.appendChild(li);
    }
}

function addCompanyMarker(company) {
    const favorites = getFavorites();
    const isFavorite = favorites[company.id];
    const icon = isFavorite ? favoriteIcon : defaultIcon;

    const marker = L.marker([company.latitude, company.longitude], { icon: icon }).addTo(map);
    markers[company.id] = marker;

    const popupContent = `
        <b>${company.name}</b><br>
        ${company.address}<br>
        <button class="favorite-btn" data-id="${company.id}" data-name="${company.name}" data-latitude="${company.latitude}" data-longitude="${company.longitude}">
            ${isFavorite ? 'お気に入り解除' : 'お気に入りに追加'}
        </button>
    `;
    marker.bindPopup(popupContent);

    marker.on('popupopen', function() {
        const btn = document.querySelector(`.favorite-btn[data-id="${company.id}"]`);
        if (btn) {
            btn.onclick = function() {
                toggleFavorite(company.id, company.name, company.latitude, company.longitude);
            };
        }
    });
}

function toggleFavorite(id, name, latitude, longitude) {
    const favorites = getFavorites();
    const marker = markers[id];

    if (favorites[id]) {
        delete favorites[id];
        if (marker) {
            marker.setIcon(defaultIcon);
            marker.setPopupContent(`
                <b>${name}</b><br>
                <button class="favorite-btn" data-id="${id}" data-name="${name}" data-latitude="${latitude}" data-longitude="${longitude}">
                    お気に入りに追加
                </button>
            `);
        }
    } else {
        favorites[id] = { name, latitude, longitude };
        if (marker) {
            marker.setIcon(favoriteIcon);
            marker.setPopupContent(`
                <b>${name}</b><br>
                <button class="favorite-btn" data-id="${id}" data-name="${name}" data-latitude="${latitude}" data-longitude="${longitude}">
                    お気に入り解除
                </button>
            `);
        }
    }
    saveFavorites(favorites);
    renderFavoritesList();
}

fetch('/api/companies')
    .then(response => response.json())
    .then(companies => {
        allCompaniesData = companies;
        allCompaniesData.forEach(company => {
            addCompanyMarker(company);
        });
        renderFavoritesList();
        
        // 初期表示でおすすめ企業を表示
        loadRecommendedCompanies();
    })
    .catch(error => console.error('Error fetching companies:', error));

// おすすめ企業を読み込む関数
function loadRecommendedCompanies() {
    fetch('/search_companies?query=')
        .then(response => response.json())
        .then(data => {
            displaySearchResults(data);
        })
        .catch(error => {
            console.error('Error loading recommended companies:', error);
        });
}

// 検索結果を表示する共通関数
function displaySearchResults(data) {
    searchResults.innerHTML = '';
    
    const companies = data.results || data; // 新しいAPIレスポンス形式に対応
    const searchCount = data.search_count || 0;
    const randomCount = data.random_count || 0;
    
    if (companies.length === 0) {
        searchResults.innerHTML = '<div style="padding: 8px;">No results found.</div>';
        return;
    }
    
    // 検索結果のヘッダーを追加
    if (searchCount > 0) {
        const searchHeader = document.createElement('div');
        searchHeader.className = 'search-section-header';
        searchHeader.textContent = `検索結果 (${searchCount}件)`;
        searchResults.appendChild(searchHeader);
    }
    
    companies.forEach((company, index) => {
        // ランダム企業のセクションヘッダーを追加（常に表示）
        if (index === searchCount && randomCount > 0) {
            const randomHeader = document.createElement('div');
            randomHeader.className = 'search-section-header random-header';
            randomHeader.textContent = `おすすめ企業 (${randomCount}件)`;
            searchResults.appendChild(randomHeader);
        }
        
        const div = document.createElement('div');
        div.className = company.is_random ? 'search-result-item random-item' : 'search-result-item';
        
        const nameDiv = document.createElement('div');
        nameDiv.className = 'search-result-name';
        nameDiv.textContent = company.name;
        
        const addressDiv = document.createElement('div');
        addressDiv.className = 'search-result-address';
        addressDiv.textContent = company.address;
        
        // ランダム企業にはアイコンを追加
        if (company.is_random) {
            const randomIcon = document.createElement('span');
            randomIcon.className = 'random-icon';
            randomIcon.textContent = '✨';
            nameDiv.appendChild(randomIcon);
        }
        
        div.appendChild(nameDiv);
        div.appendChild(addressDiv);
        
        div.dataset.latitude = company.latitude;
        div.dataset.longitude = company.longitude;
        div.addEventListener('click', () => {
            map.setView([company.latitude, company.longitude], 15);
            const foundCompany = allCompaniesData.find(c => c.name === company.name && c.latitude === company.latitude && c.longitude === company.longitude);
            if (foundCompany && markers[foundCompany.id]) {
                markers[foundCompany.id].openPopup();
            }
            // 検索結果をクリアせず、選択した企業名のみ設定
            searchInput.value = company.name;
            
            // 最寄駅とルート情報を表示
            showNearestStationInfo(company.latitude, company.longitude, company.name);
        });
        searchResults.appendChild(div);
    });
}

searchInput.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    const query = searchInput.value;

    if (query.length < 2) {
        if (query.length === 0) {
            // 空の場合はおすすめ企業を表示
            loadRecommendedCompanies();
        } else {
            // 1文字の場合は結果をクリア
            searchResults.innerHTML = '';
        }
        return;
    }

    searchTimeout = setTimeout(() => {
        fetch(`/search_companies?query=${encodeURIComponent(query)}`)
            .then(response => response.json())
            .then(data => {
                displaySearchResults(data);
            })
            .catch(error => console.error('Error searching companies:', error));
    }, 300);
});

favoritesToggleBtn.addEventListener('click', () => {
    favoritesSidebar.classList.toggle('open');
    renderFavoritesList();
});

// 検索バーの表示/非表示
searchToggleBtn.addEventListener('click', () => {
    searchContainer.classList.toggle('hidden');
});

// Mobile-specific functionality
function isMobileDevice() {
    return window.innerWidth <= 768;
}

// Close sidebar when clicking outside on mobile
document.addEventListener('click', (e) => {
    if (isMobileDevice() && favoritesSidebar.classList.contains('open')) {
        if (!favoritesSidebar.contains(e.target) && e.target !== favoritesToggleBtn) {
            favoritesSidebar.classList.remove('open');
        }
    }
});

// Close sidebar when touching the map on mobile
map.on('click', () => {
    if (isMobileDevice() && favoritesSidebar.classList.contains('open')) {
        favoritesSidebar.classList.remove('open');
    }
});

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

// Prevent zoom on double tap for search input
searchInput.addEventListener('touchend', (e) => {
    e.preventDefault();
    searchInput.focus();
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

// 登録フォームの機能
registerToggle.addEventListener('click', () => {
    const isExpanded = registerForm.classList.contains('expanded');
    
    if (isExpanded) {
        registerForm.classList.remove('expanded');
        registerForm.classList.add('collapsed');
        registerToggle.classList.remove('expanded');
        clearRegisterForm();
    } else {
        registerForm.classList.remove('collapsed');
        registerForm.classList.add('expanded');
        registerToggle.classList.add('expanded');
    }
});

cancelBtn.addEventListener('click', () => {
    registerForm.classList.remove('expanded');
    registerForm.classList.add('collapsed');
    registerToggle.classList.remove('expanded');
    clearRegisterForm();
});

registerBtn.addEventListener('click', async () => {
    const name = companyNameInput.value.trim();
    const address = companyAddressInput.value.trim();
    const corporateNumber = companyNumberInput.value.trim();
    
    if (!name || !address) {
        showRegisterMessage('企業名と住所は必須です。', 'error');
        return;
    }
    
    registerBtn.disabled = true;
    registerBtn.textContent = '登録中...';
    
    try {
        const response = await fetch('/register_company', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: name,
                address: address,
                corporate_number: corporateNumber
            })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            showRegisterMessage('企業が正常に登録されました！', 'success');
            clearRegisterForm();
            
            // 新しく登録された企業をマップに追加
            if (result.company) {
                addCompanyMarker(result.company);
                allCompaniesData.push(result.company);
                
                // 登録された企業の場所にズーム
                map.setView([result.company.latitude, result.company.longitude], 15);
                
                // マーカーのポップアップを開く
                if (markers[result.company.id]) {
                    markers[result.company.id].openPopup();
                }
            }
            
            // フォームを閉じる
            setTimeout(() => {
                registerForm.classList.remove('expanded');
                registerForm.classList.add('collapsed');
                registerToggle.classList.remove('expanded');
            }, 2000);
            
        } else {
            showRegisterMessage(result.error || '登録に失敗しました。', 'error');
        }
    } catch (error) {
        console.error('Registration error:', error);
        showRegisterMessage('ネットワークエラーが発生しました。', 'error');
    } finally {
        registerBtn.disabled = false;
        registerBtn.textContent = '登録';
    }
});

function clearRegisterForm() {
    companyNameInput.value = '';
    companyAddressInput.value = '';
    companyNumberInput.value = '';
    registerMessage.textContent = '';
    registerMessage.className = 'register-message';
}

function showRegisterMessage(message, type) {
    registerMessage.textContent = message;
    registerMessage.className = `register-message ${type}`;
    
    if (type === 'success') {
        setTimeout(() => {
            registerMessage.textContent = '';
            registerMessage.className = 'register-message';
        }, 5000);
    }
}

// ハバーサイン公式を使って距離を計算（km単位）
function calculateDistance(lat1, lng1, lat2, lng2) {
    const R = 6371; // 地球の半径 (km)
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLng = (lng2 - lng1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
              Math.sin(dLng/2) * Math.sin(dLng/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    return R * c;
}

// 最寄駅情報とルートを表示
function showNearestStationInfo(companyLat, companyLng, companyName) {
    let nearestStation = null;
    let minDistance = Infinity;
    
    // 最寄駅を検索
    tokyoStations.forEach(station => {
        const distance = calculateDistance(companyLat, companyLng, station.lat, station.lng);
        if (distance < minDistance) {
            minDistance = distance;
            nearestStation = station;
        }
    });
    
    if (nearestStation) {
        // 徒歩時間を計算（平均歩行速度 4km/h）
        const walkingTimeMinutes = Math.round((minDistance / 4) * 60);
        
        // 駅情報を表示するための要素を作成
        let stationInfoDiv = document.getElementById('station-info');
        if (!stationInfoDiv) {
            stationInfoDiv = document.createElement('div');
            stationInfoDiv.id = 'station-info';
            stationInfoDiv.style.cssText = `
                position: absolute;
                bottom: 20px;
                left: 20px;
                background: white;
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.15);
                z-index: 1000;
                max-width: 300px;
                font-size: 14px;
            `;
            document.body.appendChild(stationInfoDiv);
        }
        
        stationInfoDiv.innerHTML = `
            <h4 style="margin: 0 0 10px 0; color: #333;">${companyName}</h4>
            <div style="color: #666; margin-bottom: 8px;">
                <strong>最寄駅:</strong> ${nearestStation.name}
            </div>
            <div style="color: #666; margin-bottom: 8px;">
                <strong>徒歩時間:</strong> 約${walkingTimeMinutes}分
            </div>
            <div style="color: #666; margin-bottom: 10px;">
                <strong>路線:</strong> ${nearestStation.lines.join(', ')}
            </div>
            <button onclick="toggleRoute(${companyLat}, ${companyLng}, ${nearestStation.lat}, ${nearestStation.lng}, '${nearestStation.name}')" 
                    style="background: #007bff; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;">
                ルート表示/非表示
            </button>
        `;
        
        // 駅マーカーを追加
        const stationIcon = new L.Icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });
        
        if (window.currentStationMarker) {
            map.removeLayer(window.currentStationMarker);
        }
        
        window.currentStationMarker = L.marker([nearestStation.lat, nearestStation.lng], { icon: stationIcon })
            .addTo(map)
            .bindPopup(`<b>${nearestStation.name}</b><br>路線: ${nearestStation.lines.join(', ')}`);
    }
}

// ルート表示の切り替え
function toggleRoute(companyLat, companyLng, stationLat, stationLng, stationName) {
    if (currentRouteLayer) {
        // ルートを非表示
        map.removeLayer(currentRouteLayer);
        currentRouteLayer = null;
    } else {
        // ルートを表示
        const routeCoords = [[companyLat, companyLng], [stationLat, stationLng]];
        currentRouteLayer = L.polyline(routeCoords, {
            color: '#007bff',
            weight: 3,
            opacity: 0.7,
            dashArray: '10, 5'
        }).addTo(map);
        
        // ルート全体が見えるようにズーム調整
        map.fitBounds(routeCoords, { padding: [20, 20] });
    }
}
