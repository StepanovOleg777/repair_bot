document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('orderForm');
    const messageDiv = document.getElementById('formMessage');

    // Маска для телефона
    const phoneInput = document.getElementById('phone');
    phoneInput.addEventListener('input', function(e) {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length > 0) {
            value = '+7 (' + value;
            if (value.length > 7) value = value.slice(0, 7) + ') ' + value.slice(7);
            if (value.length > 12) value = value.slice(0, 12) + '-' + value.slice(12);
            if (value.length > 15) value = value.slice(0, 15) + '-' + value.slice(15);
            if (value.length > 18) value = value.slice(0, 18);
        }
        e.target.value = value;
    });

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Валидация
        const name = document.getElementById('name').value.trim();
        const phone = document.getElementById('phone').value.trim();
        const problem = document.getElementById('problem').value.trim();

        if (!name || !phone || !problem) {
            showMessage('Пожалуйста, заполните все обязательные поля', 'error');
            return;
        }

        // Показываем сообщение о отправке
        showMessage('Отправляем заявку...', 'info');

        // Формируем данные
        const formData = {
            name: name,
            phone: phone,
            city: document.getElementById('city').value.trim() || 'Не указан',
            service_type: document.getElementById('serviceType').value || 'other',
            problem: problem,
            source: 'website'
        };

        try {
            // Отправляем данные на API бота (локально для тестирования)
            const response = await fetch('http://localhost:3000/api/weborder', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (response.ok) {
                showMessage('✅ Заявка отправлена! Я свяжусь с вами в Telegram в течение 15 минут.', 'success');
                form.reset();

                // Через 5 секунд скрываем сообщение
                setTimeout(() => {
                    messageDiv.style.display = 'none';
                }, 5000);

            } else {
                throw new Error(data.message || 'Ошибка сервера');
            }
        } catch (error) {
            console.error('Error:', error);
            showMessage('❌ Ошибка отправки. Пожалуйста, напишите мне напрямую в Telegram: @master_repair_taganrog', 'error');
        }
    });

    function showMessage(text, type) {
        messageDiv.textContent = text;
        messageDiv.className = `form-message ${type}`;
        messageDiv.style.display = 'block';
    }

    // Плавная прокрутка к формау при клике на кнопки в будущем
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelector(this.getAttribute('href')).scrollIntoView({
                behavior: 'smooth'
            });
        });
    });
});