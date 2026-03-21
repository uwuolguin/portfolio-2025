import {
    getLanguage,
    setLoginState,
    apiRequest
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeText,
    sanitizeEmail,
    clearElement
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const loginContainer = document.getElementById('login-section');

    const translations = {
        es: {
            title: 'Iniciar Sesión',
            email: 'Correo Electrónico',
            password: 'Contraseña',
            loginButton: 'Ingresar',
            noAccount: '¿No tienes cuenta?',
            signUp: 'Regístrate aquí',
            error: 'Error al iniciar sesión',
            invalidCredentials: 'Correo o contraseña incorrectos',
            invalidEmail: 'Por favor ingresa un correo válido',
            loading: 'Ingresando...',
            resendVerification: '¿No recibiste el email de verificación?',
            resendButton: 'Reenviar email',
            verificationSent: 'Email de verificación enviado'
        },
        en: {
            title: 'Log In',
            email: 'Email',
            password: 'Password',
            loginButton: 'Log In',
            noAccount: 'Don\'t have an account?',
            signUp: 'Sign up here',
            error: 'Login error',
            invalidCredentials: 'Invalid email or password',
            invalidEmail: 'Please enter a valid email',
            loading: 'Logging in...',
            resendVerification: 'Didn\'t receive verification email?',
            resendButton: 'Resend email',
            verificationSent: 'Verification email sent'
        }
    };

    function renderLoginForm() {
        const lang = getLanguage();
        const t = translations[lang];

        clearElement(loginContainer);

        const container = document.createElement('div');
        container.className = 'login-container';

        const title = document.createElement('h2');
        title.className = 'login-title';
        title.textContent = t.title;
        container.appendChild(title);

        const form = document.createElement('form');
        form.className = 'login-form';
        form.id = 'login-form';

        // Email field
        const emailGroup = document.createElement('div');
        emailGroup.className = 'input-group';

        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.id = 'login-email';
        emailInput.name = 'email';
        emailInput.className = 'login-input';
        emailInput.placeholder = t.email;
        emailInput.required = true;
        emailInput.autocomplete = 'email';

        emailGroup.appendChild(emailInput);
        form.appendChild(emailGroup);

        // Password field
        const passwordGroup = document.createElement('div');
        passwordGroup.className = 'input-group';

        const passwordInput = document.createElement('input');
        passwordInput.type = 'password';
        passwordInput.id = 'login-password';
        passwordInput.name = 'password';
        passwordInput.className = 'login-input';
        passwordInput.placeholder = t.password;
        passwordInput.required = true;
        passwordInput.autocomplete = 'current-password';

        passwordGroup.appendChild(passwordInput);
        form.appendChild(passwordGroup);

        // Error / success message container
        // starts hidden, colour toggled between text-error and text-success
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message hidden text-error mb-sm';
        form.appendChild(errorDiv);

        // Submit button
        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.className = 'login-button';
        submitButton.textContent = t.loginButton;
        form.appendChild(submitButton);

        // Resend verification section — starts hidden
        const resendSection = document.createElement('div');
        resendSection.className = 'resend-verification-section hidden';

        const resendText = document.createElement('p');
        resendText.className = 'resend-verification-text';
        resendText.textContent = t.resendVerification;

        const resendButton = document.createElement('button');
        resendButton.type = 'button';
        resendButton.className = 'resend-verification-button';
        resendButton.textContent = t.resendButton;

        resendSection.appendChild(resendText);
        resendSection.appendChild(resendButton);
        form.appendChild(resendSection);

        // Sign-up link
        const signupSection = document.createElement('div');
        signupSection.className = 'mt-sm text-white';

        const noAccountText = document.createTextNode(t.noAccount + ' ');
        signupSection.appendChild(noAccountText);

        const signupLink = document.createElement('a');
        signupLink.href = '/sign-up/sign-up.html';
        signupLink.textContent = t.signUp;
        signupLink.className = 'text-orange no-decoration';
        signupSection.appendChild(signupLink);

        form.appendChild(signupSection);

        // Form submit handler
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            // Reset message state
            errorDiv.classList.add('hidden');
            errorDiv.classList.remove('text-success');
            errorDiv.classList.add('text-error');
            resendSection.classList.add('hidden');

            const email = sanitizeEmail(emailInput.value);
            const password = passwordInput.value;

            if (!email) {
                errorDiv.textContent = t.invalidEmail;
                errorDiv.classList.remove('hidden');
                return;
            }

            submitButton.disabled = true;
            submitButton.textContent = t.loading;

            try {
                const response = await apiRequest('/api/v1/users/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password, lang })
                });

                if (response.ok) {
                    setLoginState(true);
                    window.location.href = '/front-page/front-page.html';
                } else if (response.status === 403) {
                    const error = await response.json();
                    errorDiv.textContent = sanitizeText(error.detail) || t.invalidCredentials;
                    errorDiv.classList.remove('hidden');
                    resendSection.classList.remove('hidden');
                    submitButton.disabled = false;
                    submitButton.textContent = t.loginButton;
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || t.invalidCredentials);
                }

            } catch (error) {
                console.error('Login error:', error);
                errorDiv.textContent = sanitizeText(error.message) || t.error;
                errorDiv.classList.remove('hidden');
                submitButton.disabled = false;
                submitButton.textContent = t.loginButton;
            }
        });

        // Resend verification handler
        resendButton.addEventListener('click', async () => {
            const email = sanitizeEmail(emailInput.value);
            if (!email) {
                errorDiv.textContent = t.invalidEmail;
                errorDiv.classList.remove('text-success');
                errorDiv.classList.add('text-error');
                errorDiv.classList.remove('hidden');
                return;
            }

            resendButton.disabled = true;
            resendButton.textContent = t.loading;

            try {
                const response = await apiRequest(
                    `/api/v1/users/resend-verification?email=${encodeURIComponent(email)}`,
                    { method: 'POST' }
                );

                if (response.ok) {
                    errorDiv.classList.remove('text-error');
                    errorDiv.classList.add('text-success');
                    errorDiv.textContent = t.verificationSent;
                    errorDiv.classList.remove('hidden');
                    resendSection.classList.add('hidden');
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || t.error);
                }
            } catch (error) {
                console.error('Resend error:', error);
                errorDiv.classList.remove('text-success');
                errorDiv.classList.add('text-error');
                errorDiv.textContent = sanitizeText(error.message) || t.error;
                errorDiv.classList.remove('hidden');
            } finally {
                resendButton.disabled = false;
                resendButton.textContent = t.resendButton;
            }
        });

        container.appendChild(form);
        loginContainer.appendChild(container);
    }

    renderLoginForm();

    document.addEventListener('stateChange', renderLoginForm);
});