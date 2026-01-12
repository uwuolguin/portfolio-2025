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
    validateEmailFormat,
    sanitizePhone,
    validatePhoneFormat,
    sanitizeAPIResponse,
    buildDropdownOption,
    setSrc
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
        noImage: 'Sin imagen'
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
        noImage: 'No image'
    }
};

async function loadCurrentCompany() {
    try {
        const response = await apiRequest('/api/v1/companies/user/my-company');
        if (response.ok) {
            const data = await response.json();
            currentCompany = sanitizeAPIResponse(data);
            return currentCompany;
        }
        throw new Error('Company not found');
    } catch (error) {
        console.error('Error loading company:', error);
        return null;
    }
}

function createFilterableDropdown(id, label, options, placeholder, selectedValue = null) {
    const container = document.createElement('div');
    container.className = 'input-group';
    container.dataset.dropdownId = id;

    const selected = document.createElement('div');
    selected.className = 'dropdown-selected';

    const normalize = v => sanitizeText(String(v || '').toLowerCase());

    // Find matching option by name
    const selectedOption = options.find(opt => {
        const optName = opt.name || opt.name_es || opt.name_en || '';
        return normalize(optName) === normalize(selectedValue);
    });

    // Store the ACTUAL NAME (not UUID) as the value
    const canonicalValue = selectedOption ? (selectedOption.name || selectedOption.name_es || selectedOption.name_en || '') : '';
    selected.dataset.value = canonicalValue;

    const selectedText = document.createElement('span');
    selectedText.textContent = selectedOption ? optLabel(selectedOption) : placeholder;
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
    searchInput.placeholder = translations[getLanguage()].searchPlaceholder;
    optionsContainer.appendChild(searchInput);

    const optionsList = document.createElement('div');
    optionsList.className = 'options-list';

    options.forEach(option => {
        const label = optLabel(option);
        const optionElement = buildDropdownOption(label, label);

        optionElement.addEventListener('click', () => {
            selectedText.textContent = label;
            // Store the NAME, not UUID
            selected.dataset.value = option.name || option.name_es || option.name_en || '';
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

function optLabel(option) {
    const lang = getLanguage();
    if (lang === 'es') {
        return sanitizeText(option.name_es || option.name || '');
    } else {
        return sanitizeText(option.name_en || option.name || '');
    }
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
        
        // Get dropdown values - THESE ARE NOW COMMUNE/PRODUCT NAMES (not UUIDs)
        const communeDropdown = form.querySelector('[data-dropdown-id="commune"] .dropdown-selected');
        const productDropdown = form.querySelector('[data-dropdown-id="product"] .dropdown-selected');
        
        const communeName = communeDropdown?.dataset.value || '';
        const productName = productDropdown?.dataset.value || '';
        
        console.log('Form values:', { name, email, phone, address, communeName, productName, description });
        
        // Validate required fields
        if (!name || !email || !phone || !address || !communeName || !productName || !description) {
            alert(lang === 'es' ? 'Por favor completa todos los campos requeridos' : 'Please fill all required fields');
            submitButton.disabled = false;
            submitButton.textContent = originalText;
            return;
        }
        
        // Validate email format
        if (!validateEmailFormat(email)) {
            alert(lang === 'es' ? 'Por favor ingresa un email válido' : 'Please enter a valid email');
            submitButton.disabled = false;
            submitButton.textContent = originalText;
            return;
        }
        
        // Validate phone format
        if (!validatePhoneFormat(phone)) {
            alert(lang === 'es' ? 'Por favor ingresa un teléfono válido' : 'Please enter a valid phone');
            submitButton.disabled = false;
            submitButton.textContent = originalText;
            return;
        }
        
        // Append form data - BACKEND EXPECTS commune_name and product_name as TEXT
        formData.append('name', name);
        formData.append('email', email);
        formData.append('phone', phone);
        formData.append('address', address);
        formData.append('commune_name', communeName);  // Send NAME, not UUID
        formData.append('product_name', productName);  // Send NAME, not UUID
        formData.append('lang', lang);
        
        // Only append description for the current language
        if (lang === 'es') {
            formData.append('description_es', description);
        } else {
            formData.append('description_en', description);
        }
        
        // Append image if selected
        const imageInput = form.querySelector('[name="image"]');
        if (imageInput?.files?.[0]) {
            formData.append('image', imageInput.files[0]);
        }
        
        console.log('Submitting form data:', Object.fromEntries(formData));
        
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
            throw new Error(errorData.error?.message || t.error);
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
                window.location.href = '/publish-company/publish-company.html';
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
    messageDiv.textContent = message;
    
    container.insertBefore(messageDiv, container.firstChild);
    
    setTimeout(() => {
        messageDiv.remove();
    }, 5000);
}

async function renderEditForm() {
    const editSection = document.getElementById('profile-edit-section');
    const lang = getLanguage();
    const t = translations[lang];
    
    // Check authentication
    if (!getLoginState()) {
        editSection.innerHTML = `
            <div class="profile-edit-container">
                <h2 class="profile-edit-title">${t.title}</h2>
                <p class="login-message">
                    ${t.notLoggedIn}
                    <br><br>
                    <a href="/login/login.html">${t.loginLink}</a>
                </p>
            </div>
        `;
        return;
    }
    
    // Check if user has a company
    if (!getCompanyPublishState()) {
        editSection.innerHTML = `
            <div class="profile-edit-container">
                <h2 class="profile-edit-title">${t.title}</h2>
                <p class="no-company-message">
                    ${t.noCompany}
                    <br><br>
                    <a href="/publish-company/publish-company.html">${t.createCompanyLink}</a>
                </p>
            </div>
        `;
        return;
    }

    // Show loading
    editSection.innerHTML = `
        <div class="profile-edit-container">
            <div class="loading" style="color: white; text-align: center; padding: 2rem;">${t.loading}</div>
        </div>
    `;

    // Load company data
    const company = await loadCurrentCompany();
    if (!company) {
        editSection.innerHTML = `
            <div class="profile-edit-container">
                <p style="color: white; text-align: center;">Error loading company data</p>
            </div>
        `;
        return;
    }

    console.log('Loaded company data:', company);

    // Fetch products and communes
    const rawProducts = await fetchProducts();
    const rawCommunes = await fetchCommunes();
    const products = sanitizeAPIResponse(rawProducts);
    const communes = sanitizeAPIResponse(rawCommunes);

    // Clear and build form
    editSection.innerHTML = '';

    const container = document.createElement('div');
    container.className = 'profile-edit-container';

    const title = document.createElement('h2');
    title.className = 'profile-edit-title';
    setText(title, t.title);
    container.appendChild(title);

    // Show current image
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

    // Company name
    const nameGroup = document.createElement('div');
    nameGroup.className = 'input-group';
    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.name = 'name';
    nameInput.className = 'profile-edit-input';
    nameInput.placeholder = t.companyName;
    nameInput.value = sanitizeText(company.name || '');
    nameInput.required = true;
    nameGroup.appendChild(nameInput);
    form.appendChild(nameGroup);

    // Email
    const emailGroup = document.createElement('div');
    emailGroup.className = 'input-group';
    const emailInput = document.createElement('input');
    emailInput.type = 'email';
    emailInput.name = 'email';
    emailInput.className = 'profile-edit-input';
    emailInput.placeholder = t.email;
    emailInput.value = sanitizeEmail(company.email || '');
    emailInput.required = true;
    emailGroup.appendChild(emailInput);
    form.appendChild(emailGroup);

    // Phone
    const phoneGroup = document.createElement('div');
    phoneGroup.className = 'input-group';
    const phoneInput = document.createElement('input');
    phoneInput.type = 'tel';
    phoneInput.name = 'phone';
    phoneInput.className = 'profile-edit-input';
    phoneInput.placeholder = t.phone;
    phoneInput.value = sanitizePhone(company.phone || '');
    phoneInput.required = true;
    phoneGroup.appendChild(phoneInput);
    form.appendChild(phoneGroup);

    // Address
    const addressGroup = document.createElement('div');
    addressGroup.className = 'input-group';
    const addressInput = document.createElement('input');
    addressInput.type = 'text';
    addressInput.name = 'address';
    addressInput.className = 'profile-edit-input';
    addressInput.placeholder = t.address;
    addressInput.value = sanitizeText(company.address || '');
    addressInput.required = true;
    addressGroup.appendChild(addressInput);
    form.appendChild(addressGroup);

    // Commune dropdown - pass commune NAME from API
    const communeDropdown = createFilterableDropdown(
        'commune',
        t.commune,
        communes,
        t.selectCommune,
        company.commune_name  // This is already a NAME from the API
    );
    form.appendChild(communeDropdown);

    // Product dropdown - pass product NAME from API (in current language)
    const productDropdown = createFilterableDropdown(
        'product',
        t.product,
        products,
        t.selectProduct,
        lang === 'es' ? company.product_name_es : company.product_name_en  // This is already a NAME from the API
    );
    form.appendChild(productDropdown);

    // Description
    const descGroup = document.createElement('div');
    descGroup.className = 'input-group';
    const descTextarea = document.createElement('textarea');
    descTextarea.name = 'description';
    descTextarea.className = 'profile-edit-textarea';
    descTextarea.placeholder = t.description;
    descTextarea.rows = 4;
    descTextarea.value = sanitizeText(
        (lang === 'es' ? company.description_es : company.description_en) || ''
    );
    descTextarea.required = true;
    descGroup.appendChild(descTextarea);
    form.appendChild(descGroup);

    // Image upload
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

    // Action buttons
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

    // Add form submit handler
    form.addEventListener('submit', handleFormSubmit);

    container.appendChild(form);
    editSection.appendChild(container);
}

// Initialize on page load - ONLY ONCE
document.addEventListener('DOMContentLoaded', async () => {
    if (initialized) return;
    initialized = true;
    
    console.log('[Profile Edit] Initializing...');
    await renderEditForm();
    console.log('[Profile Edit] Initialization complete');
});