/**
 * RENDER.JS
 * Этот файл отвечает только за ОТРИСОВКУ интерфейса.
 * Он берет массив картриджей, пришедший с сервера,
 * и превращает его в HTML-карточки для двух вкладок:
 * 1) обычный список
 * 2) редактор с раскрывающимися карточками
 */

/**
 * Безопасно вставляет текст в HTML.
 * Нужна, чтобы спецсимволы не ломали верстку и не создавали лишние HTML-теги.
 * Плюс здесь используется совместимая запись для Safari/iPhone.
 *
 * @param {*} value - любое значение (строка, число, null и т.д.)
 * @returns {string} безопасная строка для вставки в шаблон
 */
function escapeHtml(value) {
    const safeValue = value === null || value === undefined ? '' : value;

    return String(safeValue)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/**
 * Определяет визуальное состояние остатка картриджа.
 * По этому результату потом подставляется цвет карточки и текст статуса.
 *
 * @param {Object} item - объект картриджа из API
 * @returns {{className: string, label: string}}
 */
function getStockState(item) {
    // Остаток меньше минимально допустимого -> красная карточка.
    if (item.quantity < item.min_qty) {
        return {
            className: 'status-low',
            label: 'К закупке'
        };
    }

    // Остаток ровно на пороге -> предупреждение.
    if (item.quantity === item.min_qty) {
        return {
            className: 'status-equal',
            label: 'Минимум'
        };
    }

    // Всё в норме -> спокойный зеленый статус.
    return {
        className: 'status-ok',
        label: 'Норма'
    };
}

/**
 * Генерирует HTML со списком штрих-кодов для карточки редактора.
 * Если штрих-кодов нет, показывает понятную заглушку.
 *
 * @param {Object} item - объект картриджа
 * @returns {string} HTML-строка для вставки в карточку
 */
function renderBarcodes(item) {
    if (!Array.isArray(item.barcodes) || item.barcodes.length === 0) {
        return '<div class="empty-barcodes">Штрих-коды еще не добавлены</div>';
    }

    return item.barcodes.map(barcode => `
        <div class="barcode-item">
            <span class="barcode-badge">${escapeHtml(barcode)}</span>
            <button type="button" class="remove-btn" onclick="removeBarcode(this, '${escapeHtml(barcode)}')">−</button>
        </div>
    `).join('');
}

/**
 * Рисует вкладку "Список расходников".
 * Здесь карточки только для просмотра: без редактирования, только статус и основные данные.
 *
 * @param {Array} data - массив картриджей из API
 */
function renderSimpleList(data) {
    // Находим контейнер, в который будут вставлены карточки.
    const list = document.getElementById('inv-list');
    if (!list) return;

    // Если сервер ничего не вернул, показываем пустое состояние.
    if (!Array.isArray(data) || data.length === 0) {
        list.innerHTML = '<div class="empty-state">Нет данных для отображения.</div>';
        return;
    }

    // Для каждого картриджа собираем HTML карточки и вставляем всё одним куском.
    list.innerHTML = data.map(item => {
        const stockState = getStockState(item);

        return `
            <article class="cartridge-card stock-card ${stockState.className}" data-search-name="${escapeHtml(item.name.toLowerCase())}">
                <div class="card-top">
                    <div class="card-heading">
                        <span class="card-id">ID ${item.id}</span>
                        <h3 class="cartridge-name">${escapeHtml(item.name)}</h3>
                    </div>
                    <span class="card-status">${item.quantity} шт</span>
                </div>

                <div class="card-metrics">
                    <div class="metric">
                        <span class="metric-label">Необходимый минимум</span>
                        <span class="metric-value">${item.min_qty} шт</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Последнее обновление</span>
                        <span class="metric-value">${escapeHtml(item.last_update || '—')}</span>
                    </div>
                </div>

                <div class="stock-note ${stockState.className}">${stockState.label}</div>
            </article>
        `;
    }).join('');
}

/**
 * Рисует вкладку "Редактор БД".
 * Здесь каждая карточка раскрывается вниз и становится редактируемой.
 * Пользователь может изменить имя, количество, минимум и штрих-коды,
 * а затем отправить изменения на сервер кнопкой "Сохранить".
 *
 * @param {Array} data - массив картриджей из API
 */
function renderEditorList(data) {
    const list = document.getElementById('editor-list');
    if (!list) return;

    if (!Array.isArray(data) || data.length === 0) {
        list.innerHTML = '<div class="empty-state">Нет картриджей для редактирования.</div>';
        return;
    }

    list.innerHTML = data.map(item => {
        const stockState = getStockState(item);

        return `
            <details class="cartridge-card editor-card ${stockState.className}" data-cartridge-id="${item.id}" data-search-name="${escapeHtml(item.name.toLowerCase())}">
                <!-- Верхняя часть карточки, которая видна всегда -->
                <summary class="editor-card-summary">
                    <div class="card-top">
                        <div class="card-heading">
                            <span class="card-id">ID ${item.id}</span>
                            <h3 class="cartridge-name">${escapeHtml(item.name)}</h3>
                        </div>
                        <span class="card-status">${item.quantity} шт</span>
                    </div>

                    <div class="card-metrics compact-metrics">
                        <div class="metric">
                            <span class="metric-label">Количество</span>
                            <span class="metric-value">${item.quantity} шт</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Изменено</span>
                            <span class="metric-value">${escapeHtml(item.last_update || '—')}</span>
                        </div>
                    </div>

                    <div class="editor-hint">Нажми на меня</div>
                </summary>

                <!-- Нижняя скрытая часть карточки: поля редактирования -->
                <div class="editor-card-body">
                    <div class="editor-form-grid">
                        <label class="editor-field editor-field-full">
                            <span>Название картриджа</span>
                            <input type="text" class="name-input" value="${escapeHtml(item.name)}" />
                        </label>

                        <label class="editor-field">
                            <span>Текущее количество</span>
                            <div class="qty-controls">
                                <button type="button" class="qty-btn" onclick="adjustNumber(this, -1)">-</button>
                                <input type="number" min="0" class="qty-input current-qty" value="${item.quantity}" />
                                <button type="button" class="qty-btn" onclick="adjustNumber(this, 1)">+</button>
                            </div>
                        </label>

                        <label class="editor-field">
                            <span>Минимальный остаток</span>
                            <div class="qty-controls">
                                <button type="button" class="qty-btn" onclick="adjustNumber(this, -1)">-</button>
                                <input type="number" min="0" class="qty-input min-qty" value="${item.min_qty}" />
                                <button type="button" class="qty-btn" onclick="adjustNumber(this, 1)">+</button>
                            </div>
                        </label>

                        <div class="editor-field editor-field-full">
                            <span>Штрих-коды</span>
                            <div class="barcodes-cell" data-cartridge-id="${item.id}">
                                <div class="barcodes-list">
                                    ${renderBarcodes(item)}
                                </div>
                                <div class="add-barcode">
                                    <input type="text" class="new-barcode-input" placeholder="Новый штрих-код">
                                    <button type="button" class="add-btn" onclick="addBarcode(this)">+</button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="editor-actions">
                        <span class="timedate-note">Последнее изменение: <span class="timedate_value">${escapeHtml(item.last_update || '—')}</span></span>
                        <button type="button" class="save-btn" onclick="saveRow(this)">Сохранить</button>
                    </div>
                </div>
            </details>
        `;
    }).join('');
}
