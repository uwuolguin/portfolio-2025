import {
    getLanguage,
    getLoginState,
    setLoginState
} from '../../../0-shared-components/utils/shared-functions.js';
import { sanitizeText, sanitizeEmail } from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const signupSection = document.getElementById('signup-section');

    const translations = {
        es: {
            title: "Regístrate",
            namePlaceholder: "Nombre",
            emailPlaceholder: "Correo",
            passwordPlaceholder: "Contraseña",
            signupButton: "Registrarse",
            alreadyLoggedTitle: "Ya tienes una cuenta activa",
            alreadyLoggedMessage: "Ya has iniciado sesión. ¿Qué te gustaría hacer?",
            goToMainPage: "Ir a la página principal",
            logout: "Cerrar sesión",
            signupError: "Error al crear la cuenta. Inténtalo de nuevo."
        },
        en: {
            title: "Sign up",
            namePlaceholder: "Name",
            emailPlaceholder: "Email",
            passwordPlaceholder: "Password",
            signupButton: "Sign up",
            alreadyLoggedTitle: "You already have an active account",
            alreadyLoggedMessage: "You're already logged in. What would you like to do?",
            goToMainPage: "Go to main page",
            logout: "Log out",
            signupError: "Error creating account. Please try again."
        }
    };

    function clearSection() {
        signupSection.textContent = '';
    }

    function renderAlreadyLoggedView() {
        const t = translations[getLanguage()];
        clearSection();

        const container = document.createElement('div');
        container.className = 'signup-container';

        const title = document.createElement('h2');
        title.className = 'signup-title';
        title.textContent = t.alreadyLoggedTitle;

        const message = document.createElement('p');
        message.className = 'already-logged-message';
        message.textContent = t.alreadyLoggedMessage;

        const actions = document.createElement('div');
        actions.className = 'signup-actions';

        const goMain = document.createElement('button');
        goMain.className = 'signup-button';
        goMain.textContent = t.goToMainPage;
        goMain.addEventListener('click', () => {
            window.location.href = '../front-page/front-page.html';
        });

        const logout = document.createElement('button');
        logout.className = 'signup-button secondary';
        logout.textContent = t.logout;
        logout.addEventListener('click', () => {
            setLoginState(false);
        });

        actions.append(goMain, logout);
        container.append(title, message, actions);
        signupSection.appendChild(container);
    }

    function renderSignupForm() {
        const lang = getLanguage();
        const t = translations[lang];
        clearSection();

        const container = document.createElement('div');
        container.className = 'signup-container';

        const title = document.createElement('h2');
        title.className = 'signup-title';
        title.textContent = t.title;

        const form = document.createElement('form');
        form.className = 'signup-form';

        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.placeholder = t.namePlaceholder;
        nameInput.required = true;
        nameInput.maxLength = 100;

        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.placeholder = t.emailPlaceholder;
        emailInput.required = true;
        emailInput.maxLength = 254;

        const passwordInput = document.createElement('input');
        passwordInput.type = 'password';
        passwordInput.placeholder = t.passwordPlaceholder;
        passwordInput.required = true;
        passwordInput.autocomplete = 'new-password';

        const submit = document.createElement('button');
        submit.type = 'submit';
        submit.className = 'signup-button';
        submit.textContent = t.signupButton;

        form.append(nameInput, emailInput, passwordInput, submit);
        container.append(title, form);
        signupSection.appendChild(container);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            submit.disabled = true;

            try {
                const response = await fetch('/api/v1/users/signup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({
                        name: nameInput.value,
                        email: emailInput.value,
                        password: passwordInput.value
                    })
                });

                if (!response.ok) throw new Error();

                alert(
                    lang === 'es'
                        ? `Cuenta creada. Revisa ${sanitizeEmail(emailInput.value)}`
                        : `Account created. Check ${sanitizeEmail(emailInput.value)}`
                );

                window.location.href = '../log-in/log-in.html';

            } catch {
                alert(t.signupError);
            } finally {
                submit.disabled = false;
            }
        });
    }

    function renderContent() {
        getLoginState() ? renderAlreadyLoggedView() : renderSignupForm();
    }

    document.addEventListener('languageChange', renderContent);
    document.addEventListener('userHasLogged', renderContent);
    renderContent();
});
