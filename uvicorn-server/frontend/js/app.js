/**
 * APP.JS
 * Это точка входа фронтенда.
 * Здесь инициализируется страница после полной загрузки:
 * - загружается основной список картриджей
 * - настраивается блок анализа расходов
 */

/**
 * Подготавливает элементы управления для вкладки анализа расходов.
 * По умолчанию в селекте ставится текущий год, а по кнопке строится карта.
 */
function initializeAnalysisControls() {
    const yearSelect = document.getElementById('analysisYear');
    const buildBtn = document.getElementById('analysisBuildBtn');
    const currentYear = new Date().getFullYear();

    if (yearSelect && !yearSelect.value) {
        yearSelect.innerHTML = `<option value="${currentYear}">${currentYear}</option>`;
        yearSelect.value = String(currentYear);
    }

    if (buildBtn) {
        buildBtn.addEventListener('click', loadExpenseHeatmap);
    }
}

window.onload = function() {
    initializeAnalysisControls();
    updateDashboard();
};

// Если когда-нибудь понадобится автообновление данных,
// можно раскомментировать строку ниже.
// setInterval(updateDashboard, 5000);