// ==UserScript==
// @name         Сокол - Автозаполнение Газпромбанк
// @namespace    http://sokol.local/
// @version      1.0
// @description  Автоматическое заполнение формы заемщика в Газпромбанк TYMY данными из приложения Сокол
// @author       Sokol App
// @match        https://gazprombank.tymy.io/*
// @grant        GM_getClipboard
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    // === UTILITY FUNCTIONS ===

    // Normalize string for comparison
    function norm(s) {
        return (s ?? '').toString().replace(/\s+/g, ' ').trim();
    }

    // Format date from YYYY-MM-DD to DD.MM.YYYY
    function formatDate(dateStr) {
        if (!dateStr) return '';
        const parts = dateStr.split('-');
        if (parts.length === 3) {
            return `${parts[2]}.${parts[1]}.${parts[0]}`;
        }
        return dateStr;
    }

    // Format phone: ensure +7 prefix
    function formatPhone(phone) {
        if (!phone) return '';
        let cleaned = phone.toString().replace(/\D/g, '');
        if (cleaned.startsWith('8') && cleaned.length === 11) {
            cleaned = '7' + cleaned.substring(1);
        }
        if (!cleaned.startsWith('7') && cleaned.length === 10) {
            cleaned = '7' + cleaned;
        }
        return '+' + cleaned;
    }

    // Format passport code XXX-XXX
    function formatPassportCode(code) {
        if (!code) return '';
        const cleaned = code.toString().replace(/\D/g, '');
        if (cleaned.length === 6) {
            return cleaned.substring(0, 3) + '-' + cleaned.substring(3);
        }
        return cleaned;
    }

    // Native setter for React inputs
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

    // Set field value with normalized comparison
    function setFieldValue(selector, value) {
        const field = document.querySelector(selector);
        if (!field) {
            console.log(`[Сокол] Field not found: ${selector}`);
            return false;
        }

        const val = (value ?? '').toString();
        setNativeValue(field, val);
        console.log(`[Сокол] Set ${selector} = ${val}`);
        return true;
    }

    // Wait for element to appear in DOM
    async function waitForElement(selector, maxWait = 3000) {
        const startTime = Date.now();
        while (Date.now() - startTime < maxWait) {
            const el = document.querySelector(selector);
            if (el) return el;
            await new Promise(r => setTimeout(r, 100));
        }
        return null;
    }

    // Set field value with wait and retry - handles autocomplete dropdowns
    async function setFieldValueAsync(selector, value) {
        if (!value) return false;

        const field = await waitForElement(selector, 2000);
        if (!field) {
            console.log(`[Сокол] Field not found after wait: ${selector}`);
            return false;
        }

        const val = (value ?? '').toString();

        // Focus first
        field.focus();
        await new Promise(r => setTimeout(r, 50));

        // Clear existing value
        field.value = '';

        // Set new value using native setter
        setNativeValue(field, val);

        // Wait for autocomplete dropdown to appear
        await new Promise(r => setTimeout(r, 300));

        // Press Escape to close any autocomplete dropdown
        field.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', keyCode: 27, bubbles: true }));
        field.dispatchEvent(new KeyboardEvent('keyup', { key: 'Escape', keyCode: 27, bubbles: true }));

        // Small delay after closing dropdown
        await new Promise(r => setTimeout(r, 100));

        // Blur to trigger validation
        field.blur();
        field.dispatchEvent(new Event('blur', { bubbles: true }));

        // Verify and retry if needed
        if (field.value !== val) {
            console.log(`[Сокол] Retry setting ${selector}`);
            field.value = val;
            field.dispatchEvent(new Event('input', { bubbles: true }));
            field.dispatchEvent(new Event('change', { bubbles: true }));
        }

        console.log(`[Сокол] Set ${selector} = ${val} (actual: ${field.value})`);
        return field.value === val;
    }

    // Click radio button
    function clickRadio(selector) {
        const radio = document.querySelector(selector);
        if (radio) {
            radio.click();
            console.log(`[Сокол] Clicked radio: ${selector}`);
            return true;
        }
        console.log(`[Сокол] Radio not found: ${selector}`);
        return false;
    }

    // Fill React-Select dropdown by typing and pressing Enter
    async function fillReactSelect(inputSelector, value) {
        if (!value) return false;

        const input = document.querySelector(inputSelector);
        if (!input) {
            console.log(`[Сокол] React-Select not found: ${inputSelector}`);
            return false;
        }

        // Focus the input
        input.focus();

        // Type the value
        setNativeValue(input, value);

        // Wait for dropdown menu to appear
        await new Promise(resolve => setTimeout(resolve, 500));

        // Press Enter to select first option
        input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', keyCode: 13, bubbles: true }));

        console.log(`[Сокол] Filled React-Select ${inputSelector} with: ${value}`);
        return true;
    }

    // === CLIPBOARD READING ===

    async function readClipboard() {
        // Try GM_getClipboard first (Tampermonkey API)
        if (typeof GM_getClipboard === 'function') {
            try {
                const text = GM_getClipboard();
                if (text) return text;
            } catch (e) {
                console.log('[Сокол] GM_getClipboard failed, trying navigator.clipboard');
            }
        }

        // Fallback to standard Web API
        if (navigator.clipboard && navigator.clipboard.readText) {
            try {
                return await navigator.clipboard.readText();
            } catch (e) {
                console.error('[Сокол] navigator.clipboard failed:', e);
            }
        }

        return null;
    }

    // === MAIN FILL FUNCTION ===

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
                showNotification('❌ В буфере не JSON данные. Скопируйте данные из CRM Сокол.', 'error');
                console.error('[Сокол] Parse error:', e);
                return;
            }

            // Check that this is Sokol data
            if (data.source !== 'sokol_bank') {
                showNotification('❌ В буфере нет данных из Сокол для банка', 'error');
                console.log('[Сокол] Expected source:"sokol_bank", got:', data.source);
                return;
            }

            console.log('[Сокол] Client data:', data);

            let filledCount = 0;

            // === PERSONAL DATA ===

            // Surname, Name, Patronymic - use async version with wait
            if (data.surname && await setFieldValueAsync('#borrower\\.client\\.last_name_input', data.surname)) filledCount++;
            if (data.name && await setFieldValueAsync('#borrower\\.client\\.first_name_input', data.name)) filledCount++;
            if (data.patronymic && await setFieldValueAsync('#borrower\\.client\\.middle_name_input', data.patronymic)) filledCount++;

            // Gender (radio)
            if (data.gender === 'Мужчина') {
                if (clickRadio('#borrower\\.client\\.gender_MALE')) filledCount++;
            } else if (data.gender === 'Женщина') {
                if (clickRadio('#borrower\\.client\\.gender_FEMALE')) filledCount++;
            }

            // Phone and Email
            if (data.phone) {
                if (await setFieldValueAsync('#borrower\\.client\\.phone', formatPhone(data.phone))) filledCount++;
            }
            if (data.email && await setFieldValueAsync('#borrower\\.client\\.email', data.email)) filledCount++;

            // Birth Date and Place
            if (data.dob) {
                if (await setFieldValueAsync('#borrower\\.client\\.birth_date', formatDate(data.dob))) filledCount++;
            }
            if (data.birth_place && await setFieldValueAsync('#borrower\\.client\\.birth_place_input', data.birth_place)) filledCount++;

            // Family Status (React-Select) - try to fill
            if (data.family_status) {
                await fillReactSelect('#react-select-6-input', data.family_status);
                filledCount++;
            }

            // === PASSPORT DATA ===

            // Series and Number combined
            if (data.passport_ser && data.passport_num) {
                const ser = String(data.passport_ser).replace(/\D/g, '').padStart(4, '0');
                const num = String(data.passport_num).replace(/\D/g, '').padStart(6, '0');
                const docNo = `${ser} ${num}`;
                if (await setFieldValueAsync('#borrower\\.passport\\.document_code', docNo)) filledCount++;
            }

            // Issue Date
            if (data.passport_date) {
                if (await setFieldValueAsync('#borrower\\.passport\\.issue_date', formatDate(data.passport_date))) filledCount++;
            }

            // Division Code
            if (data.passport_code) {
                if (await setFieldValueAsync('#borrower\\.passport\\.division_code', formatPassportCode(data.passport_code))) filledCount++;
            }

            // Issued By
            if (data.passport_issued && await setFieldValueAsync('#borrower\\.passport\\.issued_by', data.passport_issued)) filledCount++;

            // === ADDRESS ===

            if (data.addr_index && await setFieldValueAsync('#borrower\\.address\\.registration\\.postal_code', data.addr_index)) filledCount++;
            if (data.addr_city && await setFieldValueAsync('#borrower\\.address\\.registration\\.city_input', data.addr_city)) filledCount++;
            if (data.addr_city && await setFieldValueAsync('#borrower\\.address\\.registration\\.locality', data.addr_city)) filledCount++;
            if (data.addr_street && await setFieldValueAsync('#borrower\\.address\\.registration\\.street_input', data.addr_street)) filledCount++;
            if (data.addr_house && await setFieldValueAsync('#borrower\\.address\\.registration\\.house', data.addr_house)) filledCount++;
            if (data.addr_korpus && await setFieldValueAsync('#borrower\\.address\\.registration\\.block', data.addr_korpus)) filledCount++;
            if (data.addr_structure && await setFieldValueAsync('#borrower\\.address\\.registration\\.building', data.addr_structure)) filledCount++;
            if (data.addr_flat && await setFieldValueAsync('#borrower\\.address\\.registration\\.apartment_number', data.addr_flat)) filledCount++;

            // Region (React-Select)
            if (data.addr_region) {
                await fillReactSelect('#react-select-8-input', data.addr_region);
                filledCount++;
            }

            // === INCOME / EMPLOYMENT ===

            if (data.job_position && await setFieldValueAsync('#borrower\\.income\\.position_type', data.job_position)) filledCount++;
            if (data.job_company && await setFieldValueAsync('#borrower\\.income\\.org_name_input', data.job_company)) filledCount++;
            if (data.job_inn && await setFieldValueAsync('#borrower\\.income\\.org_inn_input', data.job_inn)) filledCount++;
            if (data.job_phone) {
                if (await setFieldValueAsync('#borrower\\.income\\.org_phone', formatPhone(data.job_phone))) filledCount++;
            }
            if (data.job_start_date) {
                if (await setFieldValueAsync('#borrower\\.income\\.employment_last_date', formatDate(data.job_start_date))) filledCount++;
            }
            if (data.job_income && await setFieldValueAsync('#borrower\\.income\\.income', data.job_income)) filledCount++;

            // Show result notification
            if (filledCount > 0) {
                showNotification(`✅ Заполнено ${filledCount} полей`, 'success');
            } else {
                showNotification('⚠️ Нет данных для заполнения', 'warning');
            }

        } catch (e) {
            console.error('[Сокол] Error:', e);
            showNotification('❌ Ошибка: ' + e.message, 'error');
        }
    }

    // === UI: NOTIFICATION ===

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

        // Add animation styles
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

        // Remove after 4 seconds
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transition = 'opacity 0.3s';
            setTimeout(() => notification.remove(), 300);
        }, 4000);
    }

    // === UI: FILL BUTTON ===

    function addFillButton() {
        // Prevent duplicate buttons
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

    // Initialize on page load
    if (document.readyState === 'complete') {
        addFillButton();
    } else {
        window.addEventListener('load', addFillButton);
    }

})();
