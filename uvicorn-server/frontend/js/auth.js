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
        // Пробуем загрузить данные, если сессия валидна
        const response = await fetch('/api/v1/cartridges');
        if (!response.ok) {
            // Если не авторизован, перенаправляем на логин
            window.location.href = '/admin-ui/pages/login.html';
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