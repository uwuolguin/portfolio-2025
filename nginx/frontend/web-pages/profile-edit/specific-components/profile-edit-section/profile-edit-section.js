import {
    getLanguage,
    getLoginState,
    getCompanyPublishState,
    apiRequest,
    fetchProducts,
    fetchCommunes
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeText,
    setText,
    sanitizeEmail,
    buildDropdownOption,
    setSrc,
    clearElement
} from '../../../0-shared-components/utils/sanitizer.js';

let initialized = false;
let currentCompany = null;

const translations = {
    es: {
        title: 'Editar Mi Empresa',
        companyName: 'Nombre de la Empresa',
        email: 'Correo de Contacto',
        phone: 'Teléfono',
        address: 'Dirección',
        commune: 'Comuna',
        product: 'Producto/Servicio',
        description: 'Descripción',
        image: 'Cambiar Imagen',
        selectImage: 'Seleccionar nueva imagen...',
        save: 'Guardar Cambios',
        cancel: 'Cancelar',
        delete: 'Eliminar Empresa',
        selectCommune: 'Seleccionar Comuna',
        selectProduct: 'Seleccionar Producto',
        loading: 'Cargando...',
        saving: 'Guardando...',
        success: '¡Cambios guardados exitosamente!',
        error: 'Error al guardar los cambios',
        deleteConfirm: '¿Estás seguro de que deseas eliminar tu empresa? Esta acción no se puede deshacer.',
        deleteSuccess: 'Empresa eliminada exitosamente',
        deleteError: 'Error al eliminar la empresa',
        searchPlaceholder: 'Buscar...',
        notLoggedIn: 'Debes iniciar sesión para editar tu empresa.',
        noCompany: 'No tienes una empresa registrada aún.',
        loginLink: 'Ir a Login',
        createCompanyLink: 'Crear Empresa',
        currentImage: 'Imagen Actual:',
        noImage: 'Sin imagen',
        registerHere: 'Regístrate aquí',
        noAccount: '¿No tienes cuenta?'
    },
    en: {
        title: 'Edit My Company',
        companyName: 'Company Name',
        email: 'Contact Email',
        phone: 'Phone',
        address: 'Address',
        commune: 'Commune',
        product: 'Product/Service',
        description: 'Description',
        image: 'Change Image',
        selectImage: 'Select new image...',
        save: 'Save Changes',
        cancel: 'Cancel',
        delete: 'Delete Company',
        selectCommune: 'Select Commune',
        selectProduct: 'Select Product',
        loading: 'Loading...',
        saving: 'Saving...',
        success: 'Changes saved successfully!',
        error: 'Error saving changes',
        deleteConfirm: 'Are you sure you want to delete your company? This action cannot be undone.',
        deleteSuccess: 'Company deleted successfully',
        deleteError: 'Error deleting company',
        searchPlaceholder: 'Search...',
        notLoggedIn: 'You must log in to edit your company.',
        noCompany: 'You don\'t have a registered company yet.',
        loginLink: 'Go to Login',
        createCompanyLink: 'Create Company',
        currentImage: 'Current Image:',
        noImage: 'No image',
        registerHere: 'Sign up here',
        noAccount: 'Don\'t have an account?'
    }
};

async function loadCurrentCompany() {
    try {
        const response = await apiRequest('/api/v1/companies/user/my-company');
        if (response.ok) {
            const data = await response.json();
            currentCompany = data;
            return currentCompany;
        }
        throw new Error('Company not found');
    } catch (error) {
        console.error('Error loading company:', error);
        return null;
    }
}

function createFilterableDropdown(id, options, placeholder, selectedValue = null) {
    const lang = getLanguage();
    
    // Crash if lang is not properly set
    if (lang !== 'es' && lang !== 'en') {
        throw new Error(`Language must be 'es' or 'en', got: "${lang}"`);
    }
    
    const container = document.createElement('div');
    container.className = 'input-group';
    container.dataset.dropdownId = id;

    const selected = document.createElement('div');
    selected.className = 'dropdown-selected';

    const normalize = v => sanitizeText(String(v || '').toLowerCase());

    const selectedOption = options.find(opt => {
        const spanishName = opt.name_es || '';
        const englishName = opt.name_en || '';
        const communeName = opt.name || '';
        const normalizedValue = normalize(selectedValue);
        
        return normalize(spanishName) === normalizedValue ||
               normalize(englishName) === normalizedValue ||
               normalize(communeName) === normalizedValue;
    });

    const displayValue = selectedOption ? getOptionLabel(selectedOption, lang) : '';
    selected.dataset.value = displayValue;

    const selectedText = document.createElement('span');
    selectedText.textContent = selectedOption ? getOptionLabel(selectedOption, lang) : placeholder;
    selected.appendChild(selectedText);

    const arrow = document.createElement('span');
    arrow.className = 'dropdown-arrow';
    arrow.textContent = '▼';
    selected.appendChild(arrow);

    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'dropdown-options';
    optionsContainer.style.display = 'none';

    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.className = 'dropdown-search';
    searchInput.placeholder = translations[lang].searchPlaceholder;
    optionsContainer.appendChild(searchInput);

    const optionsList = document.createElement('div');
    optionsList.className = 'options-list';

    options.forEach(option => {
        const displayName = lang === 'es' 
            ? (option.name_es || option.name)
            : (option.name_en || option.name);

        const value = lang === 'es'
            ? (option.name_es || option.name)
            : (option.name_en || option.name);
        
        // Crash if the required translation is missing for products
        if (option.name_es && option.name_en && !displayName) {
            throw new Error(`Missing ${lang} translation for product: ${JSON.stringify(option)}`);
        }

        const label = sanitizeText(displayName);
        const optionElement = buildDropdownOption(value, label);

        optionElement.addEventListener('click', () => {
            selectedText.textContent = label;
            selected.dataset.value = value;
            optionsContainer.style.display = 'none';
            container.classList.remove('dropdown-open');
        });

        optionsList.appendChild(optionElement);
    });

    optionsContainer.appendChild(optionsList);

    searchInput.addEventListener('input', e => {
        const term = normalize(e.target.value);
        optionsList.querySelectorAll('.dropdown-option').forEach(opt => {
            opt.style.display = normalize(opt.textContent).includes(term) ? 'block' : 'none';
        });
    });

    selected.addEventListener('click', e => {
        e.stopPropagation();
        document.querySelectorAll('.dropdown-options').forEach(o => o.style.display = 'none');
        document.querySelectorAll('.input-group').forEach(g => g.classList.remove('dropdown-open'));
        optionsContainer.style.display = 'block';
        container.classList.add('dropdown-open');
        searchInput.value = '';
        searchInput.focus();
        optionsList.querySelectorAll('.dropdown-option').forEach(opt => {
            opt.style.display = 'block';
        });
    });

    document.addEventListener('click', () => {
        optionsContainer.style.display = 'none';
        container.classList.remove('dropdown-open');
    });

    container.appendChild(selected);
    container.appendChild(optionsContainer);
    return container;
}

function getOptionLabel(option, lang) {
    // Crash if lang is not properly set
    if (lang !== 'es' && lang !== 'en') {
        throw new Error(`Language must be 'es' or 'en', got: "${lang}"`);
    }
    
    const displayName = lang === 'es'
        ? (option.name_es || option.name)
        : (option.name_en || option.name);
    
    if (!displayName) {
        throw new Error(`Missing ${lang} translation for option: ${JSON.stringify(option)}`);
    }
    
    return sanitizeText(displayName);
}


async function handleFormSubmit(e) {
    e.preventDefault();
    
    const lang = getLanguage();
    const t = translations[lang];
    
    const form = e.target;
    const submitButton = form.querySelector('button[type="submit"]');
    const originalText = submitButton.textContent;
    
    submitButton.disabled = true;
    submitButton.textContent = t.saving;
    
    try {
        const formData = new FormData();
        
        // Get form values
        const name = form.querySelector('[name="name"]').value.trim();
        const email = form.querySelector('[name="email"]').value.trim();
        const phone = form.querySelector('[name="phone"]').value.trim();
        const address = form.querySelector('[name="address"]').value.trim();
        const description = form.querySelector('[name="description"]').value.trim();
        
        // Get dropdown values
        const communeDropdown = form.querySelector('[data-dropdown-id="commune"] .dropdown-selected');
        const productDropdown = form.querySelector('[data-dropdown-id="product"] .dropdown-selected');

        
        const communeName = communeDropdown?.dataset.value || '';
        const productName = productDropdown?.dataset.value || '';
        
        // ONLY append fields that have values (partial update support)
        if (name) formData.append('name', name);
        if (email) formData.append('email', email);
        if (phone) formData.append('phone', phone);
        if (address) formData.append('address', address);
        if (communeName) formData.append('commune_name', communeName);
        if (productName) formData.append('product_name', productName);
        
        // CRITICAL: Send description based on CURRENT language flag
        if (description) {
            if (lang === 'es') {
                formData.append('description_es', description);
            } else {
                formData.append('description_en', description);
            }
        }
        
        // Always send lang to indicate which language we're editing
        formData.append('lang', lang);
        
        // Append image only if user selected a new one
        const imageInput = form.querySelector('[name="image"]');
        if (imageInput?.files?.[0]) {
            formData.append('image', imageInput.files[0]);
        }
        
        // Submit form
        const response = await apiRequest('/api/v1/companies/user/my-company', {
            method: 'PATCH',
            body: formData
        });
        
        if (response.ok) {
            showMessage(t.success, 'success');
            await loadCurrentCompany();
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            const errorData = await response.json();
            throw new Error(errorData.error?.message || errorData.detail || t.error);
        }
        
    } catch (error) {
        console.error('Error updating company:', error);
        showMessage(error.message || t.error, 'error');
        submitButton.disabled = false;
        submitButton.textContent = originalText;
    }
}

async function handleDelete() {
    const lang = getLanguage();
    const t = translations[lang];
    
    if (!confirm(t.deleteConfirm)) {
        return;
    }
    
    try {
        const response = await apiRequest('/api/v1/companies/user/my-company', {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showMessage(t.deleteSuccess, 'success');
            setTimeout(() => {
                window.location.href = '/publish/publish.html';
            }, 1500);
        } else {
            throw new Error(t.deleteError);
        }
    } catch (error) {
        console.error('Error deleting company:', error);
        showMessage(error.message || t.deleteError, 'error');
    }
}

function showMessage(message, type) {
    const editSection = document.getElementById('profile-edit-section');
    const container = editSection.querySelector('.profile-edit-container');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `${type}-message`;
    setText(messageDiv, message);
    
    container.insertBefore(messageDiv, container.firstChild);
    
    setTimeout(() => {
        messageDiv.remove();
    }, 5000);
}

async function renderEditForm() {
    const editSection = document.getElementById('profile-edit-section');
    const lang = getLanguage();
    
    // Crash if lang is not properly set
    if (lang !== 'es' && lang !== 'en') {
        throw new Error(`Language must be 'es' or 'en', got: "${lang}"`);
    }
    
    const t = translations[lang];
    
    if (!getLoginState()) {
        clearElement(editSection);
        
        const container = document.createElement('div');
        container.className = 'profile-edit-container';
        
        const title = document.createElement('h2');
        title.className = 'profile-edit-title';
        setText(title, t.title);
        container.appendChild(title);
        
        const message = document.createElement('p');
        message.className = 'login-message';
        setText(message, t.notLoggedIn);
        container.appendChild(message);
        
        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'profile-edit-actions';
        actionsDiv.style.marginTop = '2rem';
        
        const loginButton = document.createElement('a');
        loginButton.href = '/log-in/log-in.html';
        loginButton.className = 'profile-edit-button';
        setText(loginButton, t.loginLink);
        loginButton.style.textDecoration = 'none';
        loginButton.style.display = 'inline-block';
        actionsDiv.appendChild(loginButton);
        
        container.appendChild(actionsDiv);
        
        const signupSection = document.createElement('div');
        signupSection.style.marginTop = '1.5rem';
        signupSection.style.color = '#ffffff';
        
        const noAccountText = document.createTextNode(t.noAccount + ' ');
        signupSection.appendChild(noAccountText);
        
        const signupLink = document.createElement('a');
        signupLink.href = '/sign-up/sign-up.html';
        setText(signupLink, t.registerHere);
        signupLink.style.color = '#FF9800';
        signupLink.style.textDecoration = 'none';
        signupSection.appendChild(signupLink);
        
        container.appendChild(signupSection);
        editSection.appendChild(container);
        
        return;
    }
    
    if (!getCompanyPublishState()) {
        clearElement(editSection);
        
        const container = document.createElement('div');
        container.className = 'profile-edit-container';
        
        const title = document.createElement('h2');
        title.className = 'profile-edit-title';
        setText(title, t.title);
        container.appendChild(title);
        
        const message = document.createElement('p');
        message.className = 'no-company-message';
        setText(message, t.noCompany);
        container.appendChild(message);
        
        const createButton = document.createElement('a');
        createButton.href = '/publish/publish.html';
        createButton.className = 'profile-edit-button';
        setText(createButton, t.createCompanyLink);
        createButton.style.textDecoration = 'none';
        createButton.style.display = 'inline-block';
        createButton.style.marginTop = '1rem';
        container.appendChild(createButton);
        
        editSection.appendChild(container);
        
        return;
    }

    clearElement(editSection);
    
    const loadingContainer = document.createElement('div');
    loadingContainer.className = 'profile-edit-container';
    
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'loading';
    loadingDiv.style.color = 'white';
    loadingDiv.style.textAlign = 'center';
    loadingDiv.style.padding = '2rem';
    setText(loadingDiv, t.loading);
    
    loadingContainer.appendChild(loadingDiv);
    editSection.appendChild(loadingContainer);

    const company = await loadCurrentCompany();
    if (!company) {
        clearElement(editSection);
        
        const errorContainer = document.createElement('div');
        errorContainer.className = 'profile-edit-container';
        
        const errorP = document.createElement('p');
        errorP.style.color = 'white';
        errorP.style.textAlign = 'center';
        setText(errorP, 'Error loading company data');
        
        errorContainer.appendChild(errorP);
        editSection.appendChild(errorContainer);
        return;
    }

    const products = await fetchProducts();
    const communes = await fetchCommunes();

    clearElement(editSection);

    const container = document.createElement('div');
    container.className = 'profile-edit-container';

    const title = document.createElement('h2');
    title.className = 'profile-edit-title';
    setText(title, t.title);
    container.appendChild(title);

    if (company.image_url) {
        const imageContainer = document.createElement('div');
        imageContainer.className = 'current-image-container';
        
        const imageLabel = document.createElement('p');
        imageLabel.className = 'current-image-label';
        setText(imageLabel, t.currentImage);
        imageContainer.appendChild(imageLabel);
        
        const img = document.createElement('img');
        img.className = 'current-image';
        setSrc(img, company.image_url);
        img.alt = sanitizeText(company.name || 'Company image');
        img.onerror = function() {
            const placeholder = document.createElement('p');
            placeholder.className = 'no-image-placeholder';
            setText(placeholder, t.noImage);
            this.replaceWith(placeholder);
        };
        imageContainer.appendChild(img);
        
        container.appendChild(imageContainer);
    }

    const form = document.createElement('form');
    form.className = 'profile-edit-form';
    form.id = 'profile-edit-form';

    const nameGroup = document.createElement('div');
    nameGroup.className = 'input-group';
    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.name = 'name';
    nameInput.className = 'profile-edit-input';
    nameInput.placeholder = t.companyName;
    nameInput.value = sanitizeText(company.name || '');
    nameGroup.appendChild(nameInput);
    form.appendChild(nameGroup);

    const emailGroup = document.createElement('div');
    emailGroup.className = 'input-group';
    const emailInput = document.createElement('input');
    emailInput.type = 'email';
    emailInput.name = 'email';
    emailInput.className = 'profile-edit-input';
    emailInput.placeholder = t.email;
    emailInput.value = sanitizeEmail(company.email || '');
    emailGroup.appendChild(emailInput);
    form.appendChild(emailGroup);

    const phoneGroup = document.createElement('div');
    phoneGroup.className = 'input-group';
    const phoneInput = document.createElement('input');
    phoneInput.type = 'tel';
    phoneInput.name = 'phone';
    phoneInput.className = 'profile-edit-input';
    phoneInput.placeholder = t.phone;
    phoneInput.value = sanitizeText(company.phone || '');
    phoneGroup.appendChild(phoneInput);
    form.appendChild(phoneGroup);

    const addressGroup = document.createElement('div');
    addressGroup.className = 'input-group';
    const addressInput = document.createElement('input');
    addressInput.type = 'text';
    addressInput.name = 'address';
    addressInput.className = 'profile-edit-input';
    addressInput.placeholder = t.address;
    addressInput.value = sanitizeText(company.address || '');
    addressGroup.appendChild(addressInput);
    form.appendChild(addressGroup);

    // COMMUNE: Just use name (no name_es/name_en)
    const communeDropdown = createFilterableDropdown(
        'commune',
        communes,
        t.selectCommune,
        company.commune_name
    );
    form.appendChild(communeDropdown);

    // PRODUCT: Spanish → name_es, English → name_en, NO FALLBACK
    const productSelectedValue = lang === 'es' 
        ? company.product_name_es
        : company.product_name_en;
    
    const productDropdown = createFilterableDropdown(
        'product',
        products,
        t.selectProduct,
        productSelectedValue
    );
    form.appendChild(productDropdown);

    const descGroup = document.createElement('div');
    descGroup.className = 'input-group';
    const descTextarea = document.createElement('textarea');
    descTextarea.name = 'description';
    descTextarea.className = 'profile-edit-textarea';
    descTextarea.placeholder = t.description;
    descTextarea.rows = 4;
    // CRITICAL: Show description based on current language flag
    descTextarea.value = sanitizeText(
        (lang === 'es' ? company.description_es : company.description_en) || ''
    );
    descGroup.appendChild(descTextarea);
    form.appendChild(descGroup);

    const imageGroup = document.createElement('div');
    imageGroup.className = 'input-group';
    
    const fileWrapper = document.createElement('div');
    fileWrapper.className = 'file-input-wrapper';
    
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.id = 'company-image';
    fileInput.name = 'image';
    fileInput.className = 'file-input-hidden';
    fileInput.accept = 'image/jpeg,image/png';
    
    const fileLabel = document.createElement('label');
    fileLabel.htmlFor = 'company-image';
    fileLabel.className = 'file-input-label';
    setText(fileLabel, t.selectImage);
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files?.[0]) {
            setText(fileLabel, e.target.files[0].name);
            fileLabel.classList.add('has-file');
        } else {
            setText(fileLabel, t.selectImage);
            fileLabel.classList.remove('has-file');
        }
    });
    
    fileWrapper.appendChild(fileInput);
    fileWrapper.appendChild(fileLabel);
    imageGroup.appendChild(fileWrapper);
    form.appendChild(imageGroup);

    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'profile-edit-actions';
    
    const saveButton = document.createElement('button');
    saveButton.type = 'submit';
    saveButton.className = 'profile-edit-button';
    setText(saveButton, t.save);
    actionsDiv.appendChild(saveButton);
    
    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.className = 'profile-edit-button secondary';
    setText(cancelButton, t.cancel);
    cancelButton.addEventListener('click', () => {
        window.location.href = '/front-page/front-page.html';
    });
    actionsDiv.appendChild(cancelButton);
    
    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'profile-edit-button danger';
    setText(deleteButton, t.delete);
    deleteButton.addEventListener('click', handleDelete);
    actionsDiv.appendChild(deleteButton);
    
    form.appendChild(actionsDiv);

    form.addEventListener('submit', handleFormSubmit);

    container.appendChild(form);
    editSection.appendChild(container);
}

document.addEventListener('DOMContentLoaded', async () => {
    if (initialized) return;
    initialized = true;
    
    await renderEditForm();
});

document.addEventListener('stateChange', renderEditForm);