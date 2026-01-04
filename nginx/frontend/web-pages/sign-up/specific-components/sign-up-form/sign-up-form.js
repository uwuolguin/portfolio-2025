import {
    getLanguage,
    setLoginState,
    setCSRFToken
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeText,
    sanitizeEmail,
    validateFormData  //  ADDED
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const signupContainer = document.getElementById('signup-form-container');

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
            loading: 'Creando cuenta...',
            success: 'Cuenta creada exitosamente'
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
            loading: 'Creating account...',
            success: 'Account created successfully'
        }
    };

    function renderSignupForm() {
        const lang = getLanguage();
        const t = translations[lang];

        signupContainer.innerHTML = '';

        const form = document.createElement('form');
        form.className = 'signup-form';
        form.id = 'signup-form';

        const title = document.createElement('h2');
        title.textContent = t.title;
        form.appendChild(title);

        // Name field
        const nameGroup = document.createElement('div');
        nameGroup.className = 'form-group';

        const nameLabel = document.createElement('label');
        nameLabel.textContent = t.name;
        nameLabel.setAttribute('for', 'signup-name');

        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.id = 'signup-name';
        nameInput.name = 'name';
        nameInput.required = true;
        nameInput.autocomplete = 'name';

        nameGroup.appendChild(nameLabel);
        nameGroup.appendChild(nameInput);
        form.appendChild(nameGroup);

        // Email field
        const emailGroup = document.createElement('div');
        emailGroup.className = 'form-group';

        const emailLabel = document.createElement('label');
        emailLabel.textContent = t.email;
        emailLabel.setAttribute('for', 'signup-email');

        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.id = 'signup-email';
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
        passwordLabel.setAttribute('for', 'signup-password');

        const passwordInput = document.createElement('input');
        passwordInput.type = 'password';
        passwordInput.id = 'signup-password';
        passwordInput.name = 'password';
        passwordInput.required = true;
        passwordInput.minLength = 8;
        passwordInput.autocomplete = 'new-password';

        passwordGroup.appendChild(passwordLabel);
        passwordGroup.appendChild(passwordInput);
        form.appendChild(passwordGroup);

        // Confirm password field
        const confirmGroup = document.createElement('div');
        confirmGroup.className = 'form-group';

        const confirmLabel = document.createElement('label');
        confirmLabel.textContent = t.confirmPassword;
        confirmLabel.setAttribute('for', 'signup-confirm-password');

        const confirmInput = document.createElement('input');
        confirmInput.type = 'password';
        confirmInput.id = 'signup-confirm-password';
        confirmInput.name = 'confirmPassword';
        confirmInput.required = true;
        confirmInput.minLength = 8;
        confirmInput.autocomplete = 'new-password';

        confirmGroup.appendChild(confirmLabel);
        confirmGroup.appendChild(confirmInput);
        form.appendChild(confirmGroup);

        // Error message container
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.display = 'none';
        form.appendChild(errorDiv);

        // Submit button
        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.className = 'btn-primary';
        submitButton.textContent = t.signupButton;
        form.appendChild(submitButton);

        // Login link
        const loginLink = document.createElement('div');
        loginLink.className = 'login-link';
        
        const haveAccountText = document.createElement('span');
        haveAccountText.textContent = t.haveAccount + ' ';
        
        const loginAnchor = document.createElement('a');
        loginAnchor.href = '/log-in';
        loginAnchor.textContent = t.login;
        
        loginLink.appendChild(haveAccountText);
        loginLink.appendChild(loginAnchor);
        form.appendChild(loginLink);

        //  CRITICAL FIX: Validate and sanitize before submission
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorDiv.style.display = 'none';

            const password = passwordInput.value;
            const confirmPassword = confirmInput.value;

            // Client-side validation
            if (password.length < 8) {
                errorDiv.textContent = t.weakPassword;
                errorDiv.style.display = 'block';
                return;
            }

            if (password !== confirmPassword) {
                errorDiv.textContent = t.passwordMismatch;
                errorDiv.style.display = 'block';
                return;
            }

            try {
                //  Validate and sanitize form data
                const validatedData = validateFormData({
                    name: nameInput.value,
                    email: emailInput.value
                });

                submitButton.disabled = true;
                submitButton.textContent = t.loading;

                const response = await fetch('/api/v1/auth/signup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        name: validatedData.name,
                        email: validatedData.email,
                        password: password  // Don't sanitize passwords - preserve exact input
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    
                    if (data.csrf_token) {
                        setCSRFToken(data.csrf_token);
                    }
                    
                    setLoginState(true);
                    alert(t.success);
                    window.location.href = '/profile-view';
                } else {
                    const error = await response.json();
                    throw new Error(error.error || t.error);
                }

            } catch (error) {
                console.error('Signup error:', error);
                errorDiv.textContent = error.message || t.error;
                errorDiv.style.display = 'block';
                submitButton.disabled = false;
                submitButton.textContent = t.signupButton;
            }
        });

        signupContainer.appendChild(form);
    }

    renderSignupForm();

    document.addEventListener('languageChange', renderSignupForm);
});