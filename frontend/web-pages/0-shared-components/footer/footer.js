import { getLanguage } from '../utils/shared-functions.js';

document.addEventListener('DOMContentLoaded', () => {
    const footerContainer = document.getElementById('footer-container');

    const translations = {
        es: {
            about: "Sobre Nosotros",
            contact: "Contacto",
            privacy: "Política de Privacidad",
            terms: "Términos y Condiciones",
            flag: "us",
            img: "/files/logos/us.svg"
        },
        en: {
            about: "About Us",
            contact: "Contact",
            privacy: "Privacy Policy",
            terms: "Terms of Service",
            flag: "es",
            img: "/files/logos/es.svg" 
        }
    };

    function renderFooter() {
        const lang = getLanguage();
        footerContainer.innerHTML = `
            <div class="footer-content">
                <div class="footer-links">
                    <a href="#">${translations[lang].about}</a>
                    <a href="#">${translations[lang].contact}</a>
                    <a href="#">${translations[lang].privacy}</a>
                    <a href="#">${translations[lang].terms}</a>
                </div>
                <div class="footer-social">
                    <a href="#"><img src="/files/logos/facebook.svg" alt="Facebook"></a>
                    <a href="#"><img src="/files/logos/twitter.svg" alt="Twitter"></a>
                    <a href="#"><img src="/files/logos/instagram.svg" alt="Instagram"></a>
                </div>

            <div class="footer-bottom">
                &copy; 2025 Proveo.cl. All rights reserved.
            </div>
        `;

    }

    document.addEventListener("languageChange", () => {
        renderFooter();
    });

    renderFooter();
});