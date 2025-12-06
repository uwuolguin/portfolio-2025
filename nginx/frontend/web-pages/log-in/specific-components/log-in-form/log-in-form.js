import { getLanguage, getLoginState, setLoginState, setCSRFToken } from '../../../0-shared-components/utils/shared-functions.js';
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
            resendSuccess: "Email de verificación enviado. Revisa tu bandeja de entrada.",
            resendError: "Error al enviar el email. Verifica tu correo e intenta de nuevo.",
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
            resendSuccess: "Verification email sent. Check your inbox.",
            resendError: "Error sending email. Verify your email and try again.",
            emailRequired: "Please enter your email address",
            resending: "Sending..."
        }
    };

    function renderAlreadyLoggedView() {
        const lang = getLanguage();
        const t = translations[lang];

        const alreadyLoggedContent = `
            <div class="login-container">
                <h2 class="login-title">${t.alreadyLoggedTitle}</h2>
                <p class="already-logged-message">${t.alreadyLoggedMessage}</p>
                <div class="logged-in-actions">
                    <button id="go-to-main" class="login-button primary">${t.goToMainPage}</button>
                    <button id="logout-button" class="login-button secondary">${t.logout}</button>
                </div>
            </div>
        `;

        loginSection.innerHTML = alreadyLoggedContent;

        document.getElementById('go-to-main').addEventListener('click', () => {
            window.location.href = '../front-page/front-page.html';
        });

        document.getElementById('logout-button').addEventListener('click', () => {
            setLoginState(false);
        });
    }

    function renderLoginForm() {
        const lang = getLanguage();
        const t = translations[lang];

        const loginFormContent = `
            <div class="login-container">
                <h2 class="login-title">${t.title}</h2>
                <form id="login-form" class="login-form">
                    <div class="input-group">
                        <input type="text" id="username" class="login-input" placeholder="${t.usernamePlaceholder}" required>
                    </div>
                    <div class="input-group">
                        <input type="password" id="password" class="login-input" placeholder="${t.passwordPlaceholder}" required>
                    </div>
                    <button type="submit" class="login-button">${t.loginButton}</button>
                </form>
                
                <!-- NEW: Resend verification section -->
                <div class="resend-verification-section">
                    <p class="resend-verification-text">${t.resendVerificationLink}</p>
                    <button type="button" id="resend-verification-btn" class="resend-verification-button">
                        ${t.resendButton}
                    </button>
                </div>
            </div>
        `;

        loginSection.innerHTML = loginFormContent;

        const loginForm = document.getElementById('login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const submitButton = loginForm.querySelector('.login-button');
                const originalButtonText = submitButton.textContent;
                
                submitButton.disabled = true;
                submitButton.textContent = lang === 'es' ? 'Iniciando sesión...' : 'Logging in...';
                
                try {
                    const username = document.getElementById('username').value;
                    const password = document.getElementById('password').value;
                    
                    const response = await fetch('/api/v1/users/login', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'X-Correlation-ID': `login_${Date.now()}`
                        },
                        credentials: 'include',
                        body: JSON.stringify({ email: username, password }),
                    });

                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.detail || 'Login failed');
                    }
                    
                    const data = await response.json();
                    
                    setCSRFToken(data.csrf_token);
                    
                    setLoginState(true);
                    
                    if (!data.user.email_verified) {
                        alert(lang === 'es' ? 
                            'Por favor verifica tu correo electrónico antes de continuar.' :
                            'Please verify your email before continuing.');
                    }
                    
                    window.location.href = '../front-page/front-page.html';
                    
                } catch (error) {
                    console.error('Login error:', error);
                    const errorMsg = lang === 'es' ? 
                        'Error al iniciar sesión. Verifica tus credenciales.' : 
                        'Login error. Please check your credentials.';
                    alert(errorMsg);
                } finally {
                    submitButton.disabled = false;
                    submitButton.textContent = originalButtonText;
                }
            });
        }

        const resendBtn = document.getElementById('resend-verification-btn');
        if (resendBtn) {
            resendBtn.addEventListener('click', async () => {
                const email = document.getElementById('username').value.trim();
                
                if (!email) {
                    alert(t.emailRequired);
                    document.getElementById('username').focus();
                    return;
                }
                
                const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailRegex.test(email)) {
                    alert(lang === 'es' ? 
                        'Por favor ingresa un correo válido' : 
                        'Please enter a valid email address');
                    return;
                }
                
                const originalButtonText = resendBtn.textContent;
                resendBtn.disabled = true;
                resendBtn.textContent = t.resending;
                
                try {
                    const response = await fetch('/api/v1/users/resend-verification', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'X-Correlation-ID': `resend_verification_${Date.now()}`
                        },
                        credentials: 'include',
                        body: JSON.stringify({ email }),
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.detail || 'Resend failed');
                    }
                    
                    alert(t.resendSuccess);
                    
                } catch (error) {
                    console.error('Resend verification error:', error);
                    alert(t.resendError);
                } finally {
                    resendBtn.disabled = false;
                    resendBtn.textContent = originalButtonText;
                }
            });
        }
    }

    function renderContent() {
        const isLoggedIn = getLoginState();
        
        if (isLoggedIn) {
            renderAlreadyLoggedView();
        } else {
            renderLoginForm();
        }
    }

    document.addEventListener("languageChange", renderContent);
    document.addEventListener("userHasLogged", renderContent);

    renderContent();
});