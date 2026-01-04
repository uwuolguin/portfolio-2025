import {
    getLanguage,
    getLoginState,
    setLoginState,
    setCSRFToken,
    apiRequest  //  ADDED: Use apiRequest for correlation IDs
} from '../../../0-shared-components/utils/shared-functions.js';

//  ADDED: Import sanitizer
import {
    sanitizeText,
    sanitizeEmail
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
            loading: 'Logging in...',
            resendVerification: 'Didn\'t receive verification email?',
            resendButton: 'Resend email',
            verificationSent: 'Verification email sent'
        }
    };

    function renderLoginForm() {
        const lang = getLanguage();
        const t = translations[lang];

        loginContainer.innerHTML = '';

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

        // Error message container
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.display = 'none';
        errorDiv.style.color = '#ff6b6b';
        errorDiv.style.marginBottom = '1rem';
        form.appendChild(errorDiv);

        // Submit button
        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.className = 'login-button';
        submitButton.textContent = t.loginButton;
        form.appendChild(submitButton);

        // Resend verification section
        const resendSection = document.createElement('div');
        resendSection.className = 'resend-verification-section';
        resendSection.style.display = 'none';

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

        //  FIXED: Sanitize email input and error messages
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorDiv.style.display = 'none';
            resendSection.style.display = 'none';

            //  Sanitize email input
            const email = sanitizeEmail(emailInput.value);
            const password = passwordInput.value; // Don't sanitize passwords

            if (!email) {
                errorDiv.textContent = t.invalidCredentials;
                errorDiv.style.display = 'block';
                return;
            }

            submitButton.disabled = true;
            submitButton.textContent = t.loading;

            try {
                //  CHANGED: Use apiRequest instead of fetch
                const response = await apiRequest('/api/v1/users/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ email, password })
                });

                if (response.ok) {
                    const data = await response.json();
                    
                    if (data.csrf_token) {
                        setCSRFToken(data.csrf_token);
                    }
                    
                    setLoginState(true);
                    window.location.href = '/front-page/front-page.html';
                } else if (response.status === 403) {
                    // Email not verified
                    errorDiv.textContent = t.invalidCredentials;
                    errorDiv.style.display = 'block';
                    resendSection.style.display = 'block';
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || t.invalidCredentials);
                }

            } catch (error) {
                console.error('Login error:', error);
                //  FIXED: Sanitize error message before display
                errorDiv.textContent = sanitizeText(error.message) || t.error;
                errorDiv.style.display = 'block';
                submitButton.disabled = false;
                submitButton.textContent = t.loginButton;
            }
        });

        // Resend verification email handler
        resendButton.addEventListener('click', async () => {
            const email = sanitizeEmail(emailInput.value);
            if (!email) return;

            resendButton.disabled = true;
            resendButton.textContent = t.loading;

            try {
                //  CHANGED: Use apiRequest instead of fetch
                const response = await apiRequest('/api/v1/users/resend-verification', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ email })
                });

                if (response.ok) {
                    errorDiv.style.color = '#4CAF50';
                    errorDiv.textContent = t.verificationSent;
                    errorDiv.style.display = 'block';
                    resendSection.style.display = 'none';
                } else {
                    throw new Error(t.error);
                }
            } catch (error) {
                console.error('Resend error:', error);
                //  FIXED: Sanitize error message
                errorDiv.style.color = '#ff6b6b';
                errorDiv.textContent = sanitizeText(error.message) || t.error;
                errorDiv.style.display = 'block';
            } finally {
                resendButton.disabled = false;
                resendButton.textContent = t.resendButton;
            }
        });

        container.appendChild(form);
        loginContainer.appendChild(container);
    }

    renderLoginForm();

    document.addEventListener('languageChange', renderLoginForm);
});