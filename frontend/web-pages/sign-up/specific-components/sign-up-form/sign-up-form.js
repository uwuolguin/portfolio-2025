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
                
                // Disable button and show loading state
                submitButton.disabled = true;
                submitButton.textContent = lang === 'es' ? 'Registrando...' : 'Signing up...';
                
                try {
                    const name = document.getElementById('name').value;
                    const email = document.getElementById('email').value;
                    const password = document.getElementById('password').value;
                    
                    // TODO: Replace this mock with actual API call
                    await new Promise(resolve => setTimeout(resolve, 1500));
                    
                    // Mock success response (90% success rate for testing)
                    const mockSuccess = Math.random() > 0.1;
                    
                    if (mockSuccess) {
                        console.log("Attempting to sign up with name:", name, "and email:", email);
                        
                        // Set login state to true (auto-login after signup)
                        setLoginState(true);
                        
                        // Show success message
                        alert(t.signupSuccess);
                        
                        // Redirect to main page
                        window.location.href = '../front-page/front-page.html';
                        
                    } else {
                        // Mock error for testing
                        throw new Error("Mock signup error");
                    }
                    
                } catch (error) {
                    console.error('Signup error:', error);
                    alert(t.signupError);
                } finally {
                    // Re-enable button and restore original text
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