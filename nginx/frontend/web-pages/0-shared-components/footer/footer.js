import { getLanguage } from '../utils/shared-functions.js';

document.addEventListener('DOMContentLoaded', () => {
    const footerContainer = document.getElementById('footer-container');

    const translations = {
        es: {
            about: "Sobre Nosotros",
            contact: "Contacto",
            privacy: "Política de Privacidad",
            terms: "Términos y Condiciones"
        },
        en: {
            about: "About Us",
            contact: "Contact",
            privacy: "Privacy Policy",
            terms: "Terms of Service"
        }
    };

    function clearFooter() {
        footerContainer.textContent = '';
    }

    function renderFooter() {
        const lang = getLanguage();
        const t = translations[lang];

        clearFooter();

        const footerContent = document.createElement('div');
        footerContent.className = 'footer-content';

        // Links
        const links = document.createElement('div');
        links.className = 'footer-links';

        const linkData = [
            { text: t.about, href: '#' },
            { text: t.contact, href: '#' },
            { text: t.privacy, href: '#' },
            { text: t.terms, href: '#' }
        ];

        linkData.forEach(item => {
            const a = document.createElement('a');
            a.href = item.href;
            a.textContent = item.text;
            links.appendChild(a);
        });

        // Social icons
        const social = document.createElement('div');
        social.className = 'footer-social';

        const socials = [
            { src: '/files/logos/facebook.svg', alt: 'Facebook' },
            { src: '/files/logos/twitter.svg', alt: 'Twitter' },
            { src: '/files/logos/instagram.svg', alt: 'Instagram' }
        ];

        socials.forEach(icon => {
            const a = document.createElement('a');
            a.href = '#';

            const img = document.createElement('img');
            img.src = icon.src;
            img.alt = icon.alt;

            a.appendChild(img);
            social.appendChild(a);
        });

        // Bottom
        const bottom = document.createElement('div');
        bottom.className = 'footer-bottom';
        bottom.textContent = '© 2025 Proveo.cl. All rights reserved.';

        footerContent.appendChild(links);
        footerContent.appendChild(social);
        footerContainer.appendChild(footerContent);
        footerContainer.appendChild(bottom);
    }

    document.addEventListener('stateChange', renderFooter);
    renderFooter();
});
