import {
    getLanguage,
    getLoginState,
    setLoginState,
    setCSRFToken,
    sanitizeText,      //  ADDED
    sanitizeEmail      //  ADDED
} from '../../../0-shared-components/utils/shared-functions.js';

document.addEventListener('DOMContentLoaded', () => {
    const loginContainer = document.getElementById('login-form-container');

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
            loading: 'Ingresando...'
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
            loading: 'Logging in...'
        }
    };

    function renderLoginForm() {
        const lang = getLanguage();
        const t = translations[lang];

        loginContainer.innerHTML = '';

        const form = document.createElement('form');
        form.className = 'login-form';
        form.id = 'login-form';

        const title = document.createElement('h2');
        title.textContent = t.title;
        form.appendChild(title);

        // Email field
        const emailGroup = document.createElement('div');
        emailGroup.className = 'form-group';

        const emailLabel = document.createElement('label');
        emailLabel.textContent = t.email;
        emailLabel.setAttribute('for', 'login-email');

        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.id = 'login-email';
        emailInput.name = 'email';
        emailInput.required = true;
        emailInput.autocomplete = 'email';

        emailGroup.appendChild(emailLabel);
        emailGroup.appendChild(emailInput);
        form.appendChild(emailGroup);

        // Password field
        const passwordGroup = document.createElement('div');
        passwordGroup.className = 'form-group';

        const passwordLabel = document.createElement('label');
        passwordLabel.textContent = t.password;
        passwordLabel.setAttribute('for', 'login-password');

        const passwordInput = document.createElement('input');
        passwordInput.type = 'password';
        passwordInput.id = 'login-password';
        passwordInput.name = 'password';
        passwordInput.required = true;
        passwordInput.autocomplete = 'current-password';

        passwordGroup.appendChild(passwordLabel);
        passwordGroup.appendChild(passwordInput);
        form.appendChild(passwordGroup);

        // Error message container
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.display = 'none';
        form.appendChild(errorDiv);

        // Submit button
        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.className = 'btn-primary';
        submitButton.textContent = t.loginButton;
        form.appendChild(submitButton);

        // Sign up link
        const signupLink = document.createElement('div');
        signupLink.className = 'signup-link';
        
        const noAccountText = document.createElement('span');
        noAccountText.textContent = t.noAccount + ' ';
        
        const signupAnchor = document.createElement('a');
        signupAnchor.href = '/sign-up';
        signupAnchor.textContent = t.signUp;
        
        signupLink.appendChild(noAccountText);
        signupLink.appendChild(signupAnchor);
        form.appendChild(signupLink);

        //  CRITICAL FIX: Sanitize inputs before submission
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorDiv.style.display = 'none';

            //  Sanitize email input
            const email = sanitizeEmail(emailInput.value);
            const password = passwordInput.value; // Don't sanitize passwords - preserve exact input

            submitButton.disabled = true;
            submitButton.textContent = t.loading;

            try {
                const response = await fetch('/api/v1/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    credentials: 'include',
                    body: JSON.stringify({ email, password })
                });

                if (response.ok) {
                    const data = await response.json();
                    
                    if (data.csrf_token) {
                        setCSRFToken(data.csrf_token);
                    }
                    
                    setLoginState(true);
                    window.location.href = '/profile-view';
                } else {
                    const error = await response.json();
                    throw new Error(error.error || t.invalidCredentials);
                }

            } catch (error) {
                console.error('Login error:', error);
                errorDiv.textContent = error.message || t.error;
                errorDiv.style.display = 'block';
                submitButton.disabled = false;
                submitButton.textContent = t.loginButton;
            }
        });

        loginContainer.appendChild(form);
    }

    renderLoginForm();

    document.addEventListener('languageChange', renderLoginForm);
});