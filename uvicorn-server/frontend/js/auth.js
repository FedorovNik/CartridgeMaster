/**
 * AUTH.JS
 * Проверка аутентификации и выход из системы
 */

// Проверяем сессию при загрузке страницы
window.addEventListener('DOMContentLoaded', function() {
    checkAuth();
});

async function checkAuth() {
    try {
        const response = await fetch('/api/v1/me');
        if (!response.ok) {
            window.location.href = '/admin-ui/pages/login.html';
            return;
        }

        const data = await response.json();
        const username = data.user_dn ? data.user_dn.split('@')[0] : '';
        const userElement = document.getElementById('sidebarUsername');
        if (userElement) {
            userElement.textContent = username || 'Неизвестен';
        }
    } catch (error) {
        console.error('Ошибка проверки аутентификации:', error);
        window.location.href = '/admin-ui/pages/login.html';
    }
}

async function logout() {
    try {
        await fetch('/api/v1/logout', {
            method: 'POST'
        });
    } catch (error) {
        console.error('Ошибка при выходе:', error);
    }
    // В любом случае перенаправляем на логин
    window.location.href = '/admin-ui/pages/login.html';
}