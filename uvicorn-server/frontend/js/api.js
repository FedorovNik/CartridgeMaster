/**
 * API.JS
 * Функции для работы с API сервера (GET, POST, PATCH запросы)
 */

/**
 * Сохраняет изменения количества, минимального уровня и имени для картриджа
 * @param {HTMLElement} btn - кнопка "Сохранить" в карточке
 */
async function saveRow(btn) {
    const card = btn.closest('[data-cartridge-id]');
    if (!card) return;

    const cartridgeId = card.dataset.cartridgeId;
    if (!cartridgeId) return;

    const nameInput = card.querySelector('.name-input');
    const qtyInput = card.querySelector('.current-qty');
    const minInput = card.querySelector('.min-qty');
    const timeElement = card.querySelector('.timedate_value');

    if (!nameInput || !qtyInput || !minInput) return;

    const newName = nameInput.value.trim();
    const newQuantity = parseInt(qtyInput.value, 10) || 0;
    const newMin = parseInt(minInput.value, 10) || 0;

    if (!newName) {
        alert('Название не может быть пустым!');
        return;
    }

    btn.disabled = true;

    try {
        const response = await fetch(`/api/v1/cartridges/${cartridgeId}/stock`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                new_quantity: newQuantity,
                new_min_qty: newMin,
                new_name: newName
            })
        });

        if (!response.ok) {
            console.error('Ошибка при сохранении!');
            alert('Не удалось сохранить изменения. Попробуйте ещё раз.');
            return;
        }

        const data = await response.json();

        if (typeof data.new_stock === 'number') {
            qtyInput.value = data.new_stock;
        }
        if (typeof data.min_qty === 'number') {
            minInput.value = data.min_qty;
        }
        if (data.last_update && timeElement) {
            timeElement.innerText = data.last_update;
        }

        await updateDashboard();
    } catch (error) {
        console.error('Сетевая ошибка:', error);
        alert('Ошибка сети. Проверьте подключение и попробуйте ещё раз.');
    } finally {
        btn.disabled = false;
    }
}

/**
 * Удаляет штрих-код у картриджа
 * @param {HTMLElement} btn - кнопка минус
 * @param {string} barcode - штрих-код для удаления
 */
async function removeBarcode(btn, barcode) {
    const cell = btn.closest('.barcodes-cell');
    if (!cell) return;

    const cartridgeId = cell.dataset.cartridgeId;
    if (!cartridgeId) return;

    btn.disabled = true;
    try {
        const response = await fetch(`/api/v1/cartridges/${cartridgeId}/barcodes/${encodeURIComponent(barcode)}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            console.error('Ошибка при удалении штрих-кода!');
            alert('Не удалось удалить штрих-код. Попробуйте ещё раз.');
            return;
        }

        // Обновляем таблицу
        await updateDashboard();
    } catch (error) {
        console.error('Сетевая ошибка:', error);
        alert('Ошибка сети. Проверьте подключение и попробуйте ещё раз.');
    } finally {
        btn.disabled = false;
    }
}

/**
 * Добавляет новый штрих-код к картриджу
 * @param {HTMLElement} btn - кнопка "Добавить"
 */
async function addBarcode(btn) {
    const cell = btn.closest('.barcodes-cell');
    if (!cell) return;

    const cartridgeId = cell.dataset.cartridgeId;
    const input = cell.querySelector('.new-barcode-input');
    if (!cartridgeId || !input) return;

    const newBarcode = input.value.trim();
    if (!newBarcode) {
        alert('Введите штрих-код!');
        return;
    }

    if (!/^\d{13}$/.test(newBarcode)) {
        alert('Штрих-код должен состоять ровно из 13 цифр!');
        return;
    }

    btn.disabled = true;
    try {
        const response = await fetch(`/api/v1/cartridges/${cartridgeId}/barcodes`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ barcode: newBarcode })
        });

        if (!response.ok) {
            console.error('Ошибка при добавлении штрих-кода!');
            alert('Не удалось добавить штрих-код.\n99% что он уже есть в базе.');
            return;
        }

        input.value = ''; // Очищаем поле
        // Обновляем таблицу
        await updateDashboard();
    } catch (error) {
        console.error('Сетевая ошибка:', error);
        alert('Ошибка сети. Проверьте подключение и попробуйте ещё раз.');
    } finally {
        btn.disabled = false;
    }
}

/**
 * Загружает данные картриджей с сервера и обновляет обе вкладки карточек
 */
async function updateDashboard() {
    try {
        const listSearchInput = document.getElementById('searchInput-1');
        const editorSearchInput = document.getElementById('searchInput-2');
        const listSearchValue = listSearchInput ? listSearchInput.value : '';
        const editorSearchValue = editorSearchInput ? editorSearchInput.value : '';
        const openedCardIds = Array.from(document.querySelectorAll('#editor-list details[open]')).map(card => card.dataset.cartridgeId);

        const response = await fetch('/api/v1/cartridges');
        const data = await response.json();

        renderSimpleList(data);
        renderEditorList(data);
        initializeEditorCards();

        if (listSearchInput) {
            listSearchInput.value = listSearchValue;
            filterTable_list();
        }

        if (editorSearchInput) {
            editorSearchInput.value = editorSearchValue;
            filterTable_edit();
        }

        openedCardIds.forEach(id => {
            const card = document.querySelector(`#editor-list details[data-cartridge-id="${id}"]`);
            if (card) {
                card.setAttribute('open', 'open');
            }
        });
    } catch (error) {
        console.error('Ошибка загрузки данных:', error);
    }
}
