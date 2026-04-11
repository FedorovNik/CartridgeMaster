/**
 * LOGIN.JS
 * Обработка формы логина
 */

document.getElementById('loginForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('errorMessage');
    
    try {
        const response = await fetch('/api/v1/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });
        
        if (response.ok) {
            // Перенаправляем на главную страницу
            window.location.href = '/admin-ui/pages/index.html';
        } else {
            const error = await response.text();
            errorDiv.textContent = error || 'Ошибка авторизации';
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        console.error('Ошибка:', error);
        errorDiv.textContent = 'Ошибка сети. Попробуйте ещё раз.';
        errorDiv.style.display = 'block';
    }
});