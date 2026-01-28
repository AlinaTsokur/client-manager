// ==UserScript==
// @name         Сокол - Автозаполнение ИНН
// @namespace    http://sokol.local/
// @version      1.4
// @description  Автоматическое заполнение формы ИНН на nalog.ru данными из приложения Сокол
// @author       Sokol App
// @match        https://service.nalog.ru/inn.do*
// @grant        GM_getClipboard
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    // Нормализация строки для сравнения (убираем лишние пробелы)
    function norm(s) {
        return (s ?? '').toString().replace(/\s+/g, ' ').trim();
    }

    // Функция для форматирования даты из YYYY-MM-DD в DD.MM.YYYY
    function formatDate(dateStr) {
        if (!dateStr) return '';
        const parts = dateStr.split('-');
        if (parts.length === 3) {
            return `${parts[2]}.${parts[1]}.${parts[0]}`;
        }
        return dateStr;
    }

    // Native setter — правильная версия (ищем на прототипе)
    function setNativeValue(el, value) {
        if (!el) return false;

        const proto = Object.getPrototypeOf(el);
        const desc = Object.getOwnPropertyDescriptor(proto, 'value');

        if (desc && desc.set) {
            desc.set.call(el, value);
        } else {
            el.value = value;
        }

        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('blur', { bubbles: true }));
        return true;
    }

    // Установка значения с нормализованной проверкой результата
    function setFieldValue(selector, value) {
        const field = document.querySelector(selector);
        if (!field) return false;

        const val = (value ?? '').toString();
        setNativeValue(field, val);
        // Нормализованное сравнение — учитывает форматирование масок
        return norm(field.value) === norm(val);
    }

    // Чтение буфера обмена с fallback
    async function readClipboard() {
        // Пробуем GM_getClipboard (Tampermonkey API, более надёжный)
        if (typeof GM_getClipboard === 'function') {
            try {
                const text = GM_getClipboard();
                if (text) return text;
            } catch (e) {
                console.log('[Сокол] GM_getClipboard failed, trying navigator.clipboard');
            }
        }

        // Fallback на стандартный Web API
        if (navigator.clipboard && navigator.clipboard.readText) {
            try {
                return await navigator.clipboard.readText();
            } catch (e) {
                console.error('[Сокол] navigator.clipboard failed:', e);
            }
        }

        return null;
    }

    // Основная функция заполнения из буфера обмена
    async function fillFromClipboard() {
        try {
            const clipboardText = await readClipboard();

            if (!clipboardText) {
                showNotification('❌ Нет доступа к буферу. Разрешите Clipboard в настройках браузера.', 'error');
                return;
            }

            let data;
            try {
                data = JSON.parse(clipboardText);
            } catch (e) {
                showNotification('❌ В буфере не JSON данные', 'error');
                console.error('[Сокол] Ошибка парсинга:', e);
                return;
            }

            // Проверяем что это данные из Сокол (по полю source)
            if (data.source !== 'sokol') {
                showNotification('❌ В буфере нет данных из Сокол', 'error');
                console.log('[Сокол] Ожидался source:"sokol", получено:', data.source);
                return;
            }

            console.log('[Сокол] Данные клиента:', data);

            let filledCount = 0;

            // Заполняем фамилию
            if (data.surname && setFieldValue('#fam', data.surname)) filledCount++;
            else setFieldValue('#fam', '');

            // Заполняем имя
            if (data.name && setFieldValue('#nam', data.name)) filledCount++;
            else setFieldValue('#nam', '');

            // Заполняем отчество
            if (data.patronymic) {
                if (setFieldValue('#otch', data.patronymic)) filledCount++;
            } else {
                // Если нет отчества - СНАЧАЛА очищаем поле, ПОТОМ кликаем чекбокс
                setFieldValue('#otch', '');
                const noPatrCheckbox = document.querySelector('#unichk_0');
                if (noPatrCheckbox) {
                    // Универсальная проверка: input.checked или classList
                    const isChecked = ('checked' in noPatrCheckbox)
                        ? noPatrCheckbox.checked
                        : noPatrCheckbox.classList.contains('checked');
                    if (!isChecked) {
                        noPatrCheckbox.click();
                        console.log('[Сокол] Отмечено "Нет отчества"');
                    }
                }
            }

            // Заполняем дату рождения
            const dobFormatted = formatDate(data.dob);
            if (dobFormatted && setFieldValue('#bdate', dobFormatted)) filledCount++;
            else setFieldValue('#bdate', '');

            // Устанавливаем тип документа (21 = паспорт РФ) — напрямую для select
            const docTypeSelect = document.querySelector('#doctype');
            if (docTypeSelect) {
                docTypeSelect.value = '21';
                docTypeSelect.dispatchEvent(new Event('change', { bubbles: true }));
            }

            // Заполняем серию и номер паспорта
            if (data.passport_ser && data.passport_num) {
                const ser = String(data.passport_ser).replace(/\D/g, '').padStart(4, '0');
                const num = String(data.passport_num).replace(/\D/g, '').padStart(6, '0');
                const docNo = `${ser.substring(0, 2)} ${ser.substring(2, 4)} ${num}`;
                if (setFieldValue('#docno', docNo)) filledCount++;
            } else {
                setFieldValue('#docno', '');
            }

            // Заполняем дату выдачи паспорта
            const passDateFormatted = formatDate(data.passport_date);
            if (passDateFormatted && setFieldValue('#docdt', passDateFormatted)) filledCount++;
            else setFieldValue('#docdt', '');

            // Показываем уведомление
            if (filledCount > 0) {
                showNotification(`✅ Заполнено ${filledCount} полей`, 'success');
            } else {
                showNotification('⚠️ Нет данных для заполнения', 'warning');
            }

        } catch (e) {
            console.error('[Сокол] Ошибка:', e);
            showNotification('❌ Ошибка: ' + e.message, 'error');
        }
    }

    // Функция показа уведомления
    function showNotification(message, type = 'success') {
        const colors = {
            success: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            error: 'linear-gradient(135deg, #e74c3c 0%, #c0392b 100%)',
            warning: 'linear-gradient(135deg, #f39c12 0%, #e67e22 100%)'
        };

        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${colors[type]};
            color: white;
            padding: 15px 25px;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            z-index: 999999;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            animation: sokolSlideIn 0.3s ease-out;
        `;
        notification.textContent = message;

        // Добавляем стили анимации (один раз)
        if (!document.querySelector('#sokol-notification-style')) {
            const style = document.createElement('style');
            style.id = 'sokol-notification-style';
            style.textContent = `
                @keyframes sokolSlideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
            `;
            document.head.appendChild(style);
        }

        document.body.appendChild(notification);

        // Удаляем через 4 секунды
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transition = 'opacity 0.3s';
            setTimeout(() => notification.remove(), 300);
        }, 4000);
    }

    // Добавляем кнопку для заполнения (с защитой от дубликатов)
    function addFillButton() {
        // Защита от повторного добавления
        if (document.querySelector('#sokolFillBtn')) return;

        const btn = document.createElement('button');
        btn.id = 'sokolFillBtn';
        btn.innerHTML = '🦅 Вставить из Сокол';
        btn.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 15px 25px;
            border-radius: 30px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            z-index: 999999;
            box-shadow: 0 4px 20px rgba(102, 126, 234, 0.5);
            transition: transform 0.2s, box-shadow 0.2s;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        `;
        btn.onmouseover = () => {
            btn.style.transform = 'scale(1.05)';
            btn.style.boxShadow = '0 6px 25px rgba(102, 126, 234, 0.7)';
        };
        btn.onmouseout = () => {
            btn.style.transform = 'scale(1)';
            btn.style.boxShadow = '0 4px 20px rgba(102, 126, 234, 0.5)';
        };
        btn.onclick = fillFromClipboard;

        document.body.appendChild(btn);
    }

    // Запускаем при загрузке страницы
    if (document.readyState === 'complete') {
        addFillButton();
    } else {
        window.addEventListener('load', addFillButton);
    }

})();
