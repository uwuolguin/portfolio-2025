import {
    getLanguage,
    setLoginState,
    setCSRFToken,
    apiRequest  //  ADDED: Use apiRequest for correlation IDs
} from '../../../0-shared-components/utils/shared-functions.js';

//  ADDED: Import sanitizer
import {
    sanitizeText,
    sanitizeEmail,
    validateFormData
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
            loading: 'Creating account...',
            success: 'Account created. Please verify your email.'
        }
    };

    function renderSignupForm() {
        const lang = getLanguage();
        const t = translations[lang];

        signupContainer.innerHTML = '';

        const container = document.createElement('div');
        container.className = 'signup-container';

        const title = document.createElement('h2');
        title.className = 'signup-title';
        title.textContent = t.title;
        container.appendChild(title);

        const form = document.createElement('form');
        form.className = 'signup-form';
        form.id = 'signup-form';

        // Name field
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

        nameGroup.appendChild(nameInput);
        form.appendChild(nameGroup);

        // Email field
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

        // Password field
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

        // Confirm password field
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

        // Error message container
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.display = 'none';
        errorDiv.style.color = '#ff6b6b';
        errorDiv.style.marginBottom = '1rem';
        form.appendChild(errorDiv);

        // Success message container
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.style.display = 'none';
        successDiv.style.color = '#4CAF50';
        successDiv.style.marginBottom = '1rem';
        form.appendChild(successDiv);

        // Submit button
        const submitButton = document.createElement('button');
        submitButton.type = 'submit';
        submitButton.className = 'signup-button';
        submitButton.textContent = t.signupButton;
        form.appendChild(submitButton);

        // Login link
        const loginLink = document.createElement('div');
        loginLink.className = 'login-link';
        loginLink.style.marginTop = '1rem';
        loginLink.style.color = '#ffffff';
        
        const haveAccountText = document.createTextNode(t.haveAccount + ' ');
        loginLink.appendChild(haveAccountText);
        
        const loginAnchor = document.createElement('a');
        loginAnchor.href = '/log-in/log-in.html';
        loginAnchor.textContent = t.login;
        loginAnchor.style.color = '#FF9800';
        loginAnchor.style.textDecoration = 'none';
        
        loginLink.appendChild(loginAnchor);
        form.appendChild(loginLink);

        //  FIXED: Validate, sanitize, and use apiRequest
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorDiv.style.display = 'none';
            successDiv.style.display = 'none';

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

                //  CHANGED: Use apiRequest instead of fetch
                const response = await apiRequest('/api/v1/users/signup', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: validatedData.name,
                        email: validatedData.email,
                        password: password  // Don't sanitize passwords
                    })
                });

                if (response.ok) {
                    successDiv.textContent = t.success;
                    successDiv.style.display = 'block';
                    
                    // Redirect to login after 2 seconds
                    setTimeout(() => {
                        window.location.href = '/log-in/log-in.html';
                    }, 2000);
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || t.error);
                }

            } catch (error) {
                console.error('Signup error:', error);
                //  FIXED: Sanitize error message before display
                errorDiv.textContent = sanitizeText(error.message) || t.error;
                errorDiv.style.display = 'block';
                submitButton.disabled = false;
                submitButton.textContent = t.signupButton;
            }
        });

        container.appendChild(form);
        signupContainer.appendChild(container);
    }

    renderSignupForm();

    document.addEventListener('languageChange', renderSignupForm);
});