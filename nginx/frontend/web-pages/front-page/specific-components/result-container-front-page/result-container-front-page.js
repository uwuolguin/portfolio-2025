import {
    getLanguage,
    getLoginState,
    setLoginState,
    setCSRFToken
} from '../../../0-shared-components/utils/shared-functions.js';

document.addEventListener('DOMContentLoaded', () => {
    const loginSection = document.getElementById('login-section');

    const translations = {
        es: {
            title: "Inicia sesión",
            usernamePlaceholder: "Correo",
            passwordPlaceholder: "Contraseña",
            loginButton: "Iniciar sesión",
            alreadyLoggedTitle: "Ya has iniciado sesión",
            alreadyLoggedMessage: "Ya tienes una sesión activa. ¿Qué te gustaría hacer?",
            goToMainPage: "Ir a la página principal",
            logout: "Cerrar sesión",
            resendVerificationLink: "¿No recibiste el email de verificación?",
            resendButton: "Reenviar verificación",
            resendSuccess: "Email de verificación enviado.",
            resendError: "Error al enviar el email.",
            emailRequired: "Por favor ingresa tu correo electrónico",
            resending: "Enviando..."
        },
        en: {
            title: "Log in",
            usernamePlaceholder: "Email",
            passwordPlaceholder: "Password",
            loginButton: "Log in",
            alreadyLoggedTitle: "You're already logged in",
            alreadyLoggedMessage: "You have an active session. What would you like to do?",
            goToMainPage: "Go to main page",
            logout: "Log out",
            resendVerificationLink: "Didn't receive the verification email?",
            resendButton: "Resend verification",
            resendSuccess: "Verification email sent.",
            resendError: "Error sending email.",
            emailRequired: "Please enter your email address",
            resending: "Sending..."
        }
    };

    const clear = () => (loginSection.textContent = '');

    function renderAlreadyLoggedView() {
        const t = translations[getLanguage()];
        clear();

        const container = document.createElement('div');
        container.className = 'login-container';

        const title = document.createElement('h2');
        title.className = 'login-title';
        title.textContent = t.alreadyLoggedTitle;

        const msg = document.createElement('p');
        msg.className = 'already-logged-message';
        msg.textContent = t.alreadyLoggedMessage;

        const actions = document.createElement('div');
        actions.className = 'logged-in-actions';

        const goMain = document.createElement('button');
        goMain.className = 'login-button primary';
        goMain.textContent = t.goToMainPage;
        goMain.onclick = () => {
            window.location.href = '../front-page/front-page.html';
        };

        const logout = document.createElement('button');
        logout.className = 'login-button secondary';
        logout.textContent = t.logout;
        logout.onclick = () => setLoginState(false);

        actions.append(goMain, logout);
        container.append(title, msg, actions);
        loginSection.appendChild(container);
    }

    function renderLoginForm() {
        const lang = getLanguage();
        const t = translations[lang];
        clear();

        const container = document.createElement('div');
        container.className = 'login-container';

        const title = document.createElement('h2');
        title.className = 'login-title';
        title.textContent = t.title;

        const form = document.createElement('form');
        form.className = 'login-form';

        const email = document.createElement('input');
        email.id = 'username';
        email.type = 'email';
        email.placeholder = t.usernamePlaceholder;
        email.required = true;

        const password = document.createElement('input');
        password.id = 'password';
        password.type = 'password';
        password.placeholder = t.passwordPlaceholder;
        password.required = true;

        const submit = document.createElement('button');
        submit.type = 'submit';
        submit.className = 'login-button';
        submit.textContent = t.loginButton;

        form.append(email, password, submit);

        const resendSection = document.createElement('div');
        resendSection.className = 'resend-verification-section';

        const resendText = document.createElement('p');
        resendText.textContent = t.resendVerificationLink;

        const resendBtn = document.createElement('button');
        resendBtn.type = 'button';
        resendBtn.textContent = t.resendButton;

        resendSection.append(resendText, resendBtn);

        container.append(title, form, resendSection);
        loginSection.appendChild(container);

        form.addEventListener('submit', async e => {
            e.preventDefault();
            submit.disabled = true;

            try {
                const res = await fetch('/api/v1/users/login', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Correlation-ID': `login_${Date.now()}`
                    },
                    body: JSON.stringify({
                        email: email.value,
                        password: password.value
                    })
                });

                if (!res.ok) throw new Error();

                const data = await res.json();
                setCSRFToken(data.csrf_token);
                setLoginState(true);
                window.location.href = '../front-page/front-page.html';
            } catch {
                alert(lang === 'es'
                    ? 'Error al iniciar sesión'
                    : 'Login error');
            } finally {
                submit.disabled = false;
            }
        });

        resendBtn.addEventListener('click', async () => {
            if (!email.value) {
                alert(t.emailRequired);
                return;
            }

            resendBtn.disabled = true;
            resendBtn.textContent = t.resending;

            try {
                await fetch('/api/v1/users/resend-verification', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Correlation-ID': `resend_${Date.now()}`
                    },
                    body: JSON.stringify({ email: email.value })
                });

                alert(t.resendSuccess);
            } catch {
                alert(t.resendError);
            } finally {
                resendBtn.disabled = false;
                resendBtn.textContent = t.resendButton;
            }
        });
    }

    function render() {
        getLoginState()
            ? renderAlreadyLoggedView()
            : renderLoginForm();
    }

    document.addEventListener('languageChange', render);
    document.addEventListener('userHasLogged', render);

    render();
});
