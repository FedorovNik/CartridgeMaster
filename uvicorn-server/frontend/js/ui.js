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
}

/**
 * Увеличивает/уменьшает значение в соседнем input[type=number] на 1
 * @param {HTMLElement} btn - кнопка +/-
 * @param {number} delta - изменение (+1 или -1)
 */
function adjustNumber(btn, delta) {
    const wrapper = btn.closest('.qty-controls');
    if (!wrapper) return;

    const input = wrapper.querySelector('input[type="number"]');
    if (!input) return;

    const current = parseInt(input.value, 10);
    if (Number.isNaN(current)) return;

    const next = current + delta;
    input.value = next < 0 ? 0 : next;
}

function filterCards(inputId, selector) {
    const input = document.getElementById(inputId);
    if (!input) return;

    const searchValue = input.value.trim().toLowerCase();
    const cards = document.querySelectorAll(selector);

    cards.forEach(card => {
        const nameText = (card.dataset.searchName || '').toLowerCase();
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
