import {
    getLanguage,
    apiRequest
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeText,
    sanitizeEmail,
    clearElement
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const signupContainer = document.getElementById('signup-section');

    const translations = {
        es: {
            title: 'Crear Cuenta',
            name: 'Nombre Completo',
            email: 'Correo Electrónico',
            password: 'Contraseña',
            confirmPassword: 'Confirmar Contraseña',
            signupButton: 'Registrarse',
            haveAccount: '¿Ya tienes cuenta?',
            login: 'Inicia sesión aquí',
            error: 'Error al crear la cuenta',
            passwordMismatch: 'Las contraseñas no coinciden',
            weakPassword: 'La contraseña debe tener al menos 8 caracteres',
            invalidEmail: 'Por favor ingresa un correo válido',
            invalidName: 'Por favor ingresa tu nombre',
            loading: 'Creando cuenta...',
            success: 'Cuenta creada. Por favor verifica tu email.'
        },
        en: {
            title: 'Sign Up',
            name: 'Full Name',
            email: 'Email',
            password: 'Password',
            confirmPassword: 'Confirm Password',
            signupButton: 'Sign Up',
            haveAccount: 'Already have an account?',
            login: 'Log in here',
            error: 'Error creating account',
            passwordMismatch: 'Passwords do not match',
            weakPassword: 'Password must be at least 8 characters',
            invalidEmail: 'Please enter a valid email',
            invalidName: 'Please enter your name',
            loading: 'Creating account...',
            success: 'Account created. Please verify your email.'
        }
    };

    function renderSignupForm() {
        const lang = getLanguage();
        const t = translations[lang];

        clearElement(signupContainer);

        const container = document.createElement('div');
        container.className = 'signup-container';

        const title = document.createElement('h2');
        title.className = 'signup-title';
        title.textContent = t.title;
        container.appendChild(title);

        const form = document.createElement('form');
        form.className = 'signup-form';
        form.id = 'signup-form';

        const nameGroup = document.createElement('div');
        nameGroup.className = 'input-group';
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.id = 'signup-name';
        nameInput.name = 'name';
        nameInput.className = 'signup-input';
        nameInput.placeholder = t.name;
        nameInput.required = true;
        nameInput.autocomplete = 'name';
        nameInput.maxLength = 100;
        nameGroup.appendChild(nameInput);
        form.appendChild(nameGroup);

        const emailGroup = document.createElement('div');
        emailGroup.className = 'input-group';
        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.id = 'signup-email';
        emailInput.name = 'email';
        emailInput.className = 'signup-input';
        emailInput.placeholder = t.email;
        emailInput.required = true;
        emailInput.autocomplete = 'email';
        emailGroup.appendChild(emailInput);
        form.appendChild(emailGroup);

        const passwordGroup = document.createElement('div');
        passwordGroup.className = 'input-group';
        const passwordInput = document.createElement('input');
        passwordInput.type = 'password';
        passwordInput.id = 'signup-password';
        passwordInput.name = 'password';
        passwordInput.className = 'signup-input';
        passwordInput.placeholder = t.password;
        passwordInput.required = true;
        passwordInput.minLength = 8;
        passwordInput.autocomplete = 'new-password';
        passwordGroup.appendChild(passwordInput);
        form.appendChild(passwordGroup);

        const confirmGroup = document.createElement('div');
        confirmGroup.className = 'input-group';
        const confirmInput = document.createElement('input');
        confirmInput.type = 'password';
        confirmInput.id = 'signup-confirm-password';
        confirmInput.name = 'confirmPassword';
        confirmInput.className = 'signup-input';
        confirmInput.placeholder = t.confirmPassword;
        confirmInput.required = true;
        confirmInput.minLength = 8;
        confirmInput.autocomplete = 'new-password';
        confirmGroup.appendChild(confirmInput);
        form.appendChild(confirmGroup);

        // starts hidden, toggled between text-error and text-success
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message hidden text-error mb-sm';
        form.appendChild(errorDiv);

        const successDiv = document.createElement('div');
        successDiv.className = 'success-message hidden text-success mb-sm';
        form.appendChild(successDiv);

        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.className = 'signup-button';
        submitButton.textContent = t.signupButton;
        form.appendChild(submitButton);

        const loginSection = document.createElement('div');
        loginSection.className = 'mt-sm text-white';

        const haveAccountText = document.createTextNode(t.haveAccount + ' ');
        loginSection.appendChild(haveAccountText);

        const loginAnchor = document.createElement('a');
        loginAnchor.href = '/log-in/log-in.html';
        loginAnchor.textContent = t.login;
        loginAnchor.className = 'text-orange no-decoration';
        loginSection.appendChild(loginAnchor);
        form.appendChild(loginSection);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            errorDiv.classList.add('hidden');
            successDiv.classList.add('hidden');

            const password = passwordInput.value;
            const confirmPassword = confirmInput.value;

            if (password.length < 8) {
                errorDiv.textContent = t.weakPassword;
                errorDiv.classList.remove('hidden');
                return;
            }

            if (password !== confirmPassword) {
                errorDiv.textContent = t.passwordMismatch;
                errorDiv.classList.remove('hidden');
                return;
            }

            const sanitizedName = sanitizeText(nameInput.value.trim());
            if (!sanitizedName) {
                errorDiv.textContent = t.invalidName;
                errorDiv.classList.remove('hidden');
                return;
            }

            const sanitizedEmail = sanitizeEmail(emailInput.value);
            if (!sanitizedEmail) {
                errorDiv.textContent = t.invalidEmail;
                errorDiv.classList.remove('hidden');
                return;
            }

            submitButton.disabled = true;
            submitButton.textContent = t.loading;

            try {
                const response = await apiRequest('/api/v1/users/signup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: sanitizedName,
                        email: sanitizedEmail,
                        password: password
                    })
                });

                if (response.ok) {
                    successDiv.textContent = t.success;
                    successDiv.classList.remove('hidden');

                    nameInput.disabled = true;
                    emailInput.disabled = true;
                    passwordInput.disabled = true;
                    confirmInput.disabled = true;

                    setTimeout(() => {
                        window.location.href = '/log-in/log-in.html';
                    }, 2000);
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || t.error);
                }

            } catch (error) {
                console.error('Signup error:', error);
                errorDiv.textContent = sanitizeText(error.message) || t.error;
                errorDiv.classList.remove('hidden');
                submitButton.disabled = false;
                submitButton.textContent = t.signupButton;
            }
        });

        container.appendChild(form);
        signupContainer.appendChild(container);
    }

    renderSignupForm();

    document.addEventListener('stateChange', renderSignupForm);
});