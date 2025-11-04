import { getLanguage, getLoginState, setLoginState } from '../../../0-shared-components/utils/shared-functions.js';

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
            signupSuccess: "¡Cuenta creada exitosamente! Bienvenido.",
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
            signupSuccess: "Account created successfully! Welcome.",
            signupError: "Error creating account. Please try again."
        }
    };

    function renderAlreadyLoggedView() {
        const lang = getLanguage();
        const t = translations[lang];

        const alreadyLoggedContent = `
            <div class="signup-container">
                <h2 class="signup-title">${t.alreadyLoggedTitle}</h2>
                <p class="already-logged-message">${t.alreadyLoggedMessage}</p>
                <div class="signup-actions">
                    <button id="go-to-main" class="signup-button">${t.goToMainPage}</button>
                    <button id="logout-button" class="signup-button secondary">${t.logout}</button>
                </div>
            </div>
        `;

        signupSection.innerHTML = alreadyLoggedContent;

        // Add event listeners
        document.getElementById('go-to-main').addEventListener('click', () => {
            window.location.href = '../front-page/front-page.html';
        });

        document.getElementById('logout-button').addEventListener('click', () => {
            setLoginState(false);
            // Page will reload automatically due to storage listener
        });
    }

    function renderSignupForm() {
        const lang = getLanguage();
        const t = translations[lang];

        const signupFormContent = `
            <div class="signup-container">
                <h2 class="signup-title">${t.title}</h2>
                <form id="signup-form" class="signup-form">
                    <div class="input-group">
                        <input type="text" id="name" class="signup-input" placeholder="${t.namePlaceholder}" required>
                    </div>
                    <div class="input-group">
                        <input type="email" id="email" class="signup-input" placeholder="${t.emailPlaceholder}" required>
                    </div>
                    <div class="input-group">
                        <input type="password" id="password" class="signup-input" placeholder="${t.passwordPlaceholder}" required>
                    </div>
                    <button type="submit" class="signup-button">${t.signupButton}</button>
                </form>
            </div>
        `;

        signupSection.innerHTML = signupFormContent;

        // Attach event listener to the form
        const signupForm = document.getElementById('signup-form');
        if (signupForm) {
            signupForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const submitButton = signupForm.querySelector('.signup-button');
                const originalButtonText = submitButton.textContent;
                
                submitButton.disabled = true;
                submitButton.textContent = lang === 'es' ? 'Registrando...' : 'Signing up...';
                
                try {
                    const name = document.getElementById('name').value;
                    const email = document.getElementById('email').value;
                    const password = document.getElementById('password').value;
                    
                    const response = await fetch('/api/v1/users/signup', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'X-Correlation-ID': `signup_${Date.now()}`
                        },
                        credentials: 'include',
                        body: JSON.stringify({ name, email, password }),
                    });
                    
                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.detail || 'Signup failed');
                    }
                    
                    const data = await response.json();
                    
                    // Show success message with email verification notice
                    alert(lang === 'es' ? 
                        `¡Cuenta creada exitosamente! Se ha enviado un correo de verificación a ${email}. Por favor revisa tu bandeja de entrada.` :
                        `Account created successfully! A verification email has been sent to ${email}. Please check your inbox.`);
                    
                    // Redirect to login
                    window.location.href = '../log-in/log-in.html';
                    
                } catch (error) {
                    console.error('Signup error:', error);
                    
                    let errorMsg = t.signupError;
                    if (error.message.includes('already registered')) {
                        errorMsg = lang === 'es' ? 
                            'Este correo ya está registrado.' : 
                            'This email is already registered.';
                    }
                    
                    alert(errorMsg);
                } finally {
                    submitButton.disabled = false;
                    submitButton.textContent = originalButtonText;
                }
            });
        }
    }

    function renderContent() {
        const isLoggedIn = getLoginState();
        
        if (isLoggedIn) {
            renderAlreadyLoggedView();
        } else {
            renderSignupForm();
        }
    }

    document.addEventListener("languageChange", renderContent);
    document.addEventListener("userHasLogged", renderContent);

    renderContent();
});