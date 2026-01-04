import { 
    getLanguage, 
    getLoginState, 
    getCompanyPublishState,
    setCompanyPublishState,
    apiRequest
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeText,
    sanitizeURL,
    sanitizeEmail,
    sanitizePhone
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const profileSection = document.getElementById('profile-section');

    const translations = {
        es: {
            title: "Mi Perfil",
            companyName: "Nombre de la empresa",
            productDescription: "Descripción del producto",
            address: "Dirección",
            phone: "Teléfono de la empresa",
            companyEmail: "Correo de la empresa",
            commune: "Comuna",
            productType: "Tipo de producto",
            companyImage: "Imagen de la empresa",
            loginRequired: "Debes iniciar sesión para ver tu perfil.",
            loginHere: "Inicia sesión aquí",
            noData: "No hay datos disponibles",
            publishFirst: "Para ver los datos de tu empresa, primero debes publicarla.",
            publishCompanyHere: "Publica tu empresa aquí",
            updateProfile: "Actualizar Perfil",
            deleteProfile: "Eliminar Perfil",
            confirmDelete: "¿Estás seguro de que quieres eliminar tu perfil? Esta acción no se puede deshacer.",
            profileDeleted: "Perfil eliminado exitosamente.",
            deleteError: "Error al eliminar el perfil. Inténtalo de nuevo."
        },
        en: {
            title: "My Profile",
            companyName: "Company name",
            productDescription: "Product description",
            address: "Address",
            phone: "Company phone",
            companyEmail: "Company email",
            commune: "Commune",
            productType: "Product type",
            companyImage: "Company image",
            loginRequired: "You must log in to view your profile.",
            loginHere: "Log in here",
            noData: "No data available",
            publishFirst: "To see your company data, you must publish it first.",
            publishCompanyHere: "Publish your company here",
            updateProfile: "Update Profile",
            deleteProfile: "Delete Profile",
            confirmDelete: "Are you sure you want to delete your profile? This action cannot be undone.",
            profileDeleted: "Profile deleted successfully.",
            deleteError: "Error deleting profile. Please try again."
        }
    };

    async function fetchUserData() {
        try {
            const res = await apiRequest('/api/v1/users/me');
            return res.ok ? await res.json() : null;
        } catch {
            return null;
        }
    }

    async function fetchMyCompany() {
        try {
            const res = await apiRequest('/api/v1/companies/user/my-company');
            if (res.ok) return await res.json();
            if (res.status === 404) return null;
            return null;
        } catch {
            return null;
        }
    }

    async function handleDeleteProfile() {
        const t = translations[getLanguage()];

        if (!confirm(t.confirmDelete)) return;

        try {
            const res = await apiRequest('/api/v1/users/me', { method: 'DELETE' });
            if (!res.ok) throw new Error();

            localStorage.clear();
            alert(t.profileDeleted);
            window.location.href = '../front-page/front-page.html';
        } catch {
            alert(t.deleteError);
        }
    }

    function createInfoItem(label, value) {
        const item = document.createElement('div');
        item.className = 'info-item';

        const l = document.createElement('label');
        l.className = 'info-label';
        l.textContent = label;

        const v = document.createElement('div');
        v.className = 'info-value';
        v.textContent = value;

        item.appendChild(l);
        item.appendChild(v);
        return item;
    }

    async function renderProfileContent() {
        const lang = getLanguage();
        const t = translations[lang];

        profileSection.textContent = '';

        const container = document.createElement('div');
        container.className = 'profile-container';

        const title = document.createElement('h2');
        title.className = 'profile-title';
        title.textContent = t.title;
        container.appendChild(title);

        if (!getLoginState()) {
            const msg = document.createElement('div');
            msg.className = 'login-message';
            msg.textContent = t.loginRequired;

            msg.appendChild(document.createElement('br'));
            msg.appendChild(document.createElement('br'));

            const link = document.createElement('a');
            link.href = '../log-in/log-in.html';
            link.className = 'login-link';
            link.textContent = t.loginHere;

            msg.appendChild(link);
            container.appendChild(msg);
            profileSection.appendChild(container);
            return;
        }

        const user = await fetchUserData();
        if (!user) return;

        const userDetails = document.createElement('div');
        userDetails.className = 'user-details';

        const name = document.createElement('div');
        name.className = 'user-name';
        name.textContent = sanitizeText(user.name);

        const email = document.createElement('div');
        email.className = 'user-email';
        email.textContent = sanitizeEmail(user.email);

        userDetails.appendChild(name);
        userDetails.appendChild(email);
        container.appendChild(userDetails);

        if (!getCompanyPublishState()) {
            const msg = document.createElement('div');
            msg.className = 'login-message';
            msg.textContent = t.publishFirst;

            msg.appendChild(document.createElement('br'));
            msg.appendChild(document.createElement('br'));

            const link = document.createElement('a');
            link.href = '../publish/publish.html';
            link.className = 'login-link';
            link.textContent = t.publishCompanyHere;

            msg.appendChild(link);
            container.appendChild(msg);

            const del = document.createElement('button');
            del.className = 'profile-button delete-button';
            del.textContent = t.deleteProfile;
            del.addEventListener('click', handleDeleteProfile);

            const actions = document.createElement('div');
            actions.className = 'profile-actions';
            actions.appendChild(del);

            container.appendChild(actions);
            profileSection.appendChild(container);
            return;
        }

        const company = await fetchMyCompany();
        if (!company) {
            setCompanyPublishState(false);
            renderProfileContent();
            return;
        }

        const info = document.createElement('div');
        info.className = 'profile-info';

        info.appendChild(createInfoItem(t.companyName, sanitizeText(company.name) || t.noData));
        info.appendChild(createInfoItem(t.productDescription, sanitizeText(lang === 'es' ? company.description_es : company.description_en) || t.noData));
        info.appendChild(createInfoItem(t.address, sanitizeText(company.address) || t.noData));
        info.appendChild(createInfoItem(t.phone, sanitizePhone(company.phone) || t.noData));
        info.appendChild(createInfoItem(t.companyEmail, sanitizeEmail(company.email) || t.noData));
        info.appendChild(createInfoItem(t.commune, sanitizeText(company.commune_name) || t.noData));
        info.appendChild(createInfoItem(t.productType, sanitizeText(lang === 'es' ? company.product_name_es : company.product_name_en) || t.noData));

        const imgItem = document.createElement('div');
        imgItem.className = 'info-item';

        const imgLabel = document.createElement('label');
        imgLabel.className = 'info-label';
        imgLabel.textContent = t.companyImage;
        imgItem.appendChild(imgLabel);

        if (company.image_url) {
            const img = document.createElement('img');
            img.src = sanitizeURL(company.image_url);
            img.className = 'company-image-preview';
            img.alt = 'Company image';
            imgItem.appendChild(img);
        } else {
            const no = document.createElement('div');
            no.className = 'info-value';
            no.textContent = t.noData;
            imgItem.appendChild(no);
        }

        info.appendChild(imgItem);
        container.appendChild(info);

        const actions = document.createElement('div');
        actions.className = 'profile-actions';

        const update = document.createElement('button');
        update.className = 'profile-button update-button';
        update.textContent = t.updateProfile;
        update.addEventListener('click', () => {
            window.location.href = '../profile-edit/profile-edit.html';
        });

        const del = document.createElement('button');
        del.className = 'profile-button delete-button';
        del.textContent = t.deleteProfile;
        del.addEventListener('click', handleDeleteProfile);

        actions.appendChild(update);
        actions.appendChild(del);
        container.appendChild(actions);

        profileSection.appendChild(container);
    }

    document.addEventListener('companyDataUpdated', renderProfileContent);
    document.addEventListener('languageChange', renderProfileContent);
    document.addEventListener('userHasLogged', renderProfileContent);
    document.addEventListener('companyPublishStateChange', renderProfileContent);

    renderProfileContent();
});
