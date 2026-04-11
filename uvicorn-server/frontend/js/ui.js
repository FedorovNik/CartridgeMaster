/**
 * UI.JS
 * Функции для управления пользовательским интерфейсом (навигация, фильтрация)
 */

/**
 * Показывает нужную секцию и обновляет активное меню
 * @param {string} sectionId - ID секции для отображения
 * @param {HTMLElement} clickedBtn - кнопка меню, на которую нажали
 */
function showSection(sectionId, clickedBtn) {
    updateDashboard();

    const sections = document.querySelectorAll('.content-section');
    sections.forEach(sec => sec.classList.remove('active-section'));

    const buttons = document.querySelectorAll('.nav-btn');
    buttons.forEach(btn => btn.classList.remove('active'));

    document.getElementById(sectionId).classList.add('active-section');
    clickedBtn.classList.add('active');

    // При открытии вкладки анализа сразу подгружаем тепловую карту за выбранный год.
    if (sectionId === 'section-analysis' && typeof loadExpenseHeatmap === 'function') {
        loadExpenseHeatmap();
    }
}

/**
 * Увеличивает/уменьшает значение в соседнем input[type=number] на 1
 * @param {HTMLElement} btn - кнопка +/-
 * @param {number} delta - изменение (+1 или -1)
 */
function adjustNumber(btn, delta) {
    // Находим ближайший родительский элемент с классом .qty-controls
    const wrapper = btn.closest('.qty-controls');
    if (!wrapper) return;
    // Находим внутри этого wrapper input[type=number] и изменяем его значение
    const input = wrapper.querySelector('input[type="number"]');
    if (!input) return;
    // Получаем текущее значение
    const current = parseInt(input.value, 10);
    if (Number.isNaN(current)) return;
    // Вычисляем новое значение и не позволяем ему стать меньше 0
    const next = current + delta;
    input.value = next < 0 ? 0 : next;
}

function filterCards(inputId, selector) {
    // Получаем значение из поля ввода и все карточки по селектору
    const input = document.getElementById(inputId);
    // На всякий случай проверяем, что элемент найден
    if (!input) return;
    // Обрезаем пробелы и приводим к нижнему регистру для нечувствительного поиска
    const searchValue = input.value.trim().toLowerCase();
    // Получаем все карточки, которые нужно фильтровать по переданному селектору
    const cards = document.querySelectorAll(selector);
    // Для каждой карточки проверяем.. 
    cards.forEach(card => {
        // Содержит ли она в своем data-атрибуте search-name искомое значение.
        // Если нет то загоняем пустоту в строку с именем
        const nameText = (card.dataset.searchName || '').toLowerCase();
        // Если содержит, то делаем сброс её inline стиля, передавая ''
        // Если нет - скрываем через display none
        card.style.display = nameText.includes(searchValue) ? '' : 'none';
    });
}

/**
 * Фильтрует карточки во вкладке "Список расходников"
 */
function filterTable_list() {
    filterCards('searchInput-1', '#inv-list .cartridge-card');
}

/**
 * Фильтрует карточки во вкладке "Редактор БД"
 */
function filterTable_edit() {
    filterCards('searchInput-2', '#editor-list .cartridge-card');
}

/**
 * Делает раскрытие карточек редактора более аккуратным: одна открыта, остальные закрыты
 */
function initializeEditorCards() {
    const editorCards = document.querySelectorAll('#editor-list details.editor-card');

    editorCards.forEach(card => {
        card.addEventListener('toggle', () => {
            if (!card.open) return;

            editorCards.forEach(otherCard => {
                if (otherCard !== card) {
                    otherCard.removeAttribute('open');
                }
            });
        });
    });
}
