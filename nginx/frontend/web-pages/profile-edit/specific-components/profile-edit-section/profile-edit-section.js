import {
    getLanguage,
    getLoginState,
    getCompanyPublishState,
    setCompanyData,
    fetchProducts,
    fetchCommunes,
    apiRequest
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeText,
    sanitizeURL,
    sanitizeEmail,
    sanitizePhone
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const profileEditSection = document.getElementById('profile-edit-section');

    const translations = {
        es: {
            title: 'Editar perfil de empresa',
            companyName: 'Nombre de la empresa',
            productDescription: 'Descripción del producto',
            address: 'Dirección',
            phone: 'Teléfono de la empresa',
            companyEmail: 'Correo de la empresa',
            commune: 'Comuna',
            productType: 'Tipo de producto',
            updateButton: 'Actualizar',
            cancelButton: 'Cancelar',
            deleteButton: 'Eliminar empresa',
            selectImage: '📷 Cambiar imagen de la empresa',
            currentImage: 'Imagen actual:',
            noImage: 'No hay imagen seleccionada',
            updateSuccess: '¡Perfil actualizado exitosamente!',
            updateError: 'Error al actualizar el perfil.',
            deleteSuccess: '¡Empresa eliminada exitosamente!',
            deleteError: 'Error al eliminar la empresa.',
            deleteConfirm: '¿Estás seguro? Esta acción no se puede deshacer.',
            loginRequired: 'Debes iniciar sesión para editar tu perfil.',
            loginHere: 'Inicia sesión aquí',
            noCompany: 'No tienes una empresa publicada.',
            publishCompany: 'Publicar empresa',
            noCompanyMessage: 'Primero debes publicar una empresa.',
            updating: 'Actualizando...',
            deleting: 'Eliminando...',
            searchCommunePlaceholder: 'Buscar comuna...',
            searchProductPlaceholder: 'Buscar producto...',
            loading: 'Cargando...'
        },
        en: {
            title: 'Edit company profile',
            companyName: 'Company name',
            productDescription: 'Product description',
            address: 'Address',
            phone: 'Company phone',
            companyEmail: 'Company email',
            commune: 'Commune',
            productType: 'Product type',
            updateButton: 'Update',
            cancelButton: 'Cancel',
            deleteButton: 'Delete company',
            selectImage: '📷 Change company image',
            currentImage: 'Current image:',
            noImage: 'No image selected',
            updateSuccess: 'Profile updated successfully!',
            updateError: 'Error updating profile.',
            deleteSuccess: 'Company deleted successfully!',
            deleteError: 'Error deleting company.',
            deleteConfirm: 'Are you sure? This cannot be undone.',
            loginRequired: 'You must log in to edit your profile.',
            loginHere: 'Log in here',
            noCompany: 'No published company found.',
            publishCompany: 'Publish company',
            noCompanyMessage: 'You must publish a company first.',
            updating: 'Updating...',
            deleting: 'Deleting...',
            searchCommunePlaceholder: 'Search commune...',
            searchProductPlaceholder: 'Search product...',
            loading: 'Loading...'
        }
    };

    async function fetchMyCompany() {
        try {
            const res = await apiRequest('/api/v1/companies/user/my-company');
            if (res.ok) return await res.json();
            if (res.status === 404) return null;
            throw new Error();
        } catch {
            return null;
        }
    }

    function createDropdown(options, placeholder, id, defaultText, currentValue) {
        const dropdown = document.createElement('div');
        dropdown.className = 'filterable-dropdown';
        dropdown.dataset.dropdownId = id;

        const selected = document.createElement('div');
        selected.className = 'dropdown-selected';
        selected.dataset.value = sanitizeText(currentValue || '');
        selected.textContent = sanitizeText(currentValue || defaultText);

        const arrow = document.createElement('span');
        arrow.className = 'dropdown-arrow';
        arrow.textContent = '▼';
        selected.appendChild(arrow);

        const optionsBox = document.createElement('div');
        optionsBox.className = 'dropdown-options';
        optionsBox.style.display = 'none';

        const search = document.createElement('input');
        search.className = 'dropdown-search';
        search.placeholder = placeholder;

        const list = document.createElement('div');
        list.className = 'options-list';

        options.forEach(opt => {
            const o = document.createElement('div');
            o.className = 'dropdown-option';
            o.dataset.value = sanitizeText(opt);
            o.textContent = sanitizeText(opt);
            list.appendChild(o);
        });

        optionsBox.appendChild(search);
        optionsBox.appendChild(list);
        dropdown.appendChild(selected);
        dropdown.appendChild(optionsBox);

        return dropdown;
    }

    async function renderEditForm() {
        const lang = getLanguage();
        const t = translations[lang];

        profileEditSection.textContent = '';

        const company = await fetchMyCompany();
        if (!company) return renderNoCompany();

        const products = await fetchProducts();
        const communes = await fetchCommunes();

        const productNames = products.map(p =>
            sanitizeText(lang === 'es' ? p.name_es : p.name_en)
        );
        const communeNames = communes.map(c => sanitizeText(c.name));

        const container = document.createElement('div');
        container.className = 'profile-edit-container';

        const title = document.createElement('h2');
        title.textContent = t.title;
        container.appendChild(title);

        const form = document.createElement('form');
        form.id = 'profile-edit-form';

        function input(id, value, placeholder, type = 'text') {
            const g = document.createElement('div');
            g.className = 'input-group';
            const i = document.createElement('input');
            i.id = id;
            i.type = type;
            i.value = sanitizeText(value || '');
            i.placeholder = placeholder;
            i.required = true;
            g.appendChild(i);
            return g;
        }

        form.appendChild(input('companyName', company.name, t.companyName));
        form.appendChild(input('address', company.address, t.address));
        form.appendChild(input('phone', sanitizePhone(company.phone), t.phone));
        form.appendChild(input('companyEmail', sanitizeEmail(company.email), t.companyEmail, 'email'));

        const communeDrop = createDropdown(
            communeNames,
            t.searchCommunePlaceholder,
            'commune',
            t.commune,
            communes.find(c => c.uuid === company.commune_uuid)?.name
        );

        const productDrop = createDropdown(
            productNames,
            t.searchProductPlaceholder,
            'product',
            t.productType,
            products.find(p => p.uuid === company.product_uuid)?.[lang === 'es' ? 'name_es' : 'name_en']
        );

        const cg = document.createElement('div');
        cg.className = 'input-group';
        cg.appendChild(communeDrop);

        const pg = document.createElement('div');
        pg.className = 'input-group';
        pg.appendChild(productDrop);

        form.appendChild(cg);
        form.appendChild(pg);

        const imgGroup = document.createElement('div');
        imgGroup.className = 'input-group';

        if (company.image_url) {
            const img = document.createElement('img');
            img.src = sanitizeURL(company.image_url);
            img.className = 'current-image';
            imgGroup.appendChild(img);
        }

        form.appendChild(imgGroup);

        const actions = document.createElement('div');
        actions.className = 'profile-edit-actions';

        ['updateButton', 'cancelButton', 'deleteButton'].forEach(key => {
            const b = document.createElement('button');
            b.type = key === 'updateButton' ? 'submit' : 'button';
            b.textContent = t[key];
            actions.appendChild(b);
        });

        form.appendChild(actions);
        container.appendChild(form);
        profileEditSection.appendChild(container);
    }

    function renderNoCompany() {
        const t = translations[getLanguage()];
        profileEditSection.textContent = '';
        const d = document.createElement('div');
        d.textContent = t.noCompanyMessage;
        profileEditSection.appendChild(d);
    }

    async function renderContent() {
        if (!getLoginState()) return;
        if (!getCompanyPublishState()) return renderNoCompany();
        await renderEditForm();
    }

    document.addEventListener('languageChange', renderContent);
    document.addEventListener('companyDataChange', renderContent);

    renderContent();
});
