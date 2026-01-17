import {
    getLanguage,
    getLoginState,
    apiRequest,
    fetchProducts,
    fetchCommunes,
    getCSRFToken
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeText,
    sanitizeEmail,
    sanitizePhone,
    sanitizeAPIResponse,
    buildDropdownOption,
    clearElement
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', async () => {
    const publishSection = document.getElementById('publish-section');

    const translations = {
        es: {
            title: 'Publicar Mi Empresa',
            companyName: 'Nombre de la Empresa',
            email: 'Correo de Contacto',
            phone: 'Teléfono',
            address: 'Dirección',
            commune: 'Comuna',
            product: 'Producto/Servicio',
            description: 'Descripción',
            image: 'Imagen de la Empresa',
            selectImage: 'Seleccionar imagen...',
            publish: 'Publicar',
            cancel: 'Cancelar',
            selectCommune: 'Seleccionar Comuna',
            selectProduct: 'Seleccionar Producto',
            loading: 'Cargando...',
            publishing: 'Publicando...',
            success: '¡Empresa publicada exitosamente!',
            error: 'Error al publicar la empresa',
            alreadyPublished: 'Ya tienes una empresa publicada',
            viewCompany: 'Ver Mi Empresa',
            loginRequired: 'Debes iniciar sesión para publicar tu empresa',
            loginHere: 'Iniciar sesión aquí',
            registerHere: 'Regístrate aquí',
            noAccount: '¿No tienes cuenta?',
            searchPlaceholder: 'Buscar...',
            requiredField: 'Este campo es requerido',
            invalidEmail: 'Correo electrónico inválido',
            selectRequired: 'Por favor selecciona una opción'
        },
        en: {
            title: 'Publish My Company',
            companyName: 'Company Name',
            email: 'Contact Email',
            phone: 'Phone',
            address: 'Address',
            commune: 'Commune',
            product: 'Product/Service',
            description: 'Description',
            image: 'Company Image',
            selectImage: 'Select image...',
            publish: 'Publish',
            cancel: 'Cancel',
            selectCommune: 'Select Commune',
            selectProduct: 'Select Product',
            loading: 'Loading...',
            publishing: 'Publishing...',
            success: 'Company published successfully!',
            error: 'Error publishing company',
            alreadyPublished: 'You already have a published company',
            viewCompany: 'View My Company',
            loginRequired: 'You must log in to publish your company',
            loginHere: 'Log in here',
            registerHere: 'Sign up here',
            noAccount: 'Don\'t have an account?',
            searchPlaceholder: 'Search...',
            requiredField: 'This field is required',
            invalidEmail: 'Invalid email address',
            selectRequired: 'Please select an option'
        }
    };

    async function checkExistingCompany() {
        try {
            const response = await apiRequest('/api/v1/companies/user/my-company');
            return response.ok;
        } catch (error) {
            return false;
        }
    }

    function createFilterableDropdown(id, options, placeholder, searchPlaceholder) {
        const container = document.createElement('div');
        container.className = 'input-group';
        container.dataset.dropdownId = id;

        const dropdownWrapper = document.createElement('div');
        dropdownWrapper.className = 'filterable-dropdown';

        const selected = document.createElement('div');
        selected.className = 'dropdown-selected';
        selected.dataset.value = '';
        
        const selectedText = document.createElement('span');
        selectedText.textContent = placeholder;
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
        searchInput.placeholder = searchPlaceholder;
        optionsContainer.appendChild(searchInput);

        const optionsList = document.createElement('div');
        optionsList.className = 'options-list';

        const lang = getLanguage();
        options.forEach(option => {
            const displayName = lang === 'es' 
                ? (option.name_es || option.name_en || option.name || '')
                : (option.name_en || option.name_es || option.name || '');
            const value = option.name_es || option.name_en || option.name || option.uuid || '';
            
            const optionElement = buildDropdownOption(value, displayName);
            
            optionElement.addEventListener('click', () => {
                selectedText.textContent = displayName;
                selected.dataset.value = value;
                optionsContainer.style.display = 'none';
                container.classList.remove('dropdown-open');
            });
            
            optionsList.appendChild(optionElement);
        });

        optionsContainer.appendChild(optionsList);

        searchInput.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const allOptions = optionsList.querySelectorAll('.dropdown-option');
            
            allOptions.forEach(opt => {
                const text = opt.textContent.toLowerCase();
                opt.style.display = text.includes(searchTerm) ? 'block' : 'none';
            });
        });

        searchInput.addEventListener('click', (e) => {
            e.stopPropagation();
        });

        selected.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = optionsContainer.style.display === 'block';
            
            document.querySelectorAll('.dropdown-options').forEach(opt => {
                opt.style.display = 'none';
            });
            document.querySelectorAll('.input-group').forEach(grp => {
                grp.classList.remove('dropdown-open');
            });
            
            if (!isOpen) {
                optionsContainer.style.display = 'block';
                container.classList.add('dropdown-open');
                searchInput.value = '';
                searchInput.focus();
                optionsList.querySelectorAll('.dropdown-option').forEach(opt => {
                    opt.style.display = 'block';
                });
            }
        });

        dropdownWrapper.appendChild(selected);
        dropdownWrapper.appendChild(optionsContainer);
        container.appendChild(dropdownWrapper);

        return container;
    }

    async function renderPublishForm() {
        const lang = getLanguage() || 'es';
        const t = translations[lang] || translations.es;

        // ============================================
        // CHECK AUTHENTICATION FIRST
        // ============================================
        const isLoggedIn = getLoginState();
        
        if (!isLoggedIn) {
            clearElement(publishSection);
            
            const container = document.createElement('div');
            container.className = 'publish-container';
            
            const title = document.createElement('h2');
            title.className = 'publish-title';
            title.textContent = t.title;
            container.appendChild(title);
            
            const message = document.createElement('p');
            message.className = 'login-message';
            message.textContent = t.loginRequired;
            container.appendChild(message);
            
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'publish-actions';
            actionsDiv.style.marginTop = '2rem';
            
            const loginButton = document.createElement('a');
            loginButton.href = '/log-in/log-in.html';
            loginButton.className = 'publish-button';
            loginButton.textContent = t.loginHere;
            loginButton.style.textDecoration = 'none';
            loginButton.style.display = 'inline-block';
            actionsDiv.appendChild(loginButton);
            
            const signupSection = document.createElement('div');
            signupSection.style.marginTop = '1.5rem';
            signupSection.style.color = '#ffffff';
            
            const noAccountText = document.createTextNode(t.noAccount + ' ');
            signupSection.appendChild(noAccountText);
            
            const signupLink = document.createElement('a');
            signupLink.href = '/sign-up/sign-up.html';
            signupLink.textContent = t.registerHere;
            signupLink.style.color = '#FF9800';
            signupLink.style.textDecoration = 'none';
            signupSection.appendChild(signupLink);
            
            container.appendChild(actionsDiv);
            container.appendChild(signupSection);
            publishSection.appendChild(container);
            
            return; // BLOCK EXECUTION HERE - DON'T LOAD FORM
        }

        clearElement(publishSection);
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'loading';
        loadingDiv.style.color = 'white';
        loadingDiv.style.textAlign = 'center';
        loadingDiv.style.padding = '2rem';
        loadingDiv.textContent = t.loading;
        publishSection.appendChild(loadingDiv);

        const hasCompany = await checkExistingCompany();
        if (hasCompany) {
            clearElement(publishSection);
            
            const container = document.createElement('div');
            container.className = 'publish-container';
            
            const message = document.createElement('p');
            message.className = 'already-published-message';
            message.textContent = t.alreadyPublished;
            
            const viewButton = document.createElement('button');
            viewButton.className = 'publish-button';
            viewButton.textContent = t.viewCompany;
            viewButton.addEventListener('click', () => {
                window.location.href = '/profile-view/profile-view.html';
            });
            
            container.appendChild(message);
            container.appendChild(viewButton);
            publishSection.appendChild(container);
            return;
        }

        const rawProducts = await fetchProducts();
        const rawCommunes = await fetchCommunes();
        const products = sanitizeAPIResponse(rawProducts);
        const communes = sanitizeAPIResponse(rawCommunes);

        clearElement(publishSection);

        const container = document.createElement('div');
        container.className = 'publish-container';

        const title = document.createElement('h2');
        title.className = 'publish-title';
        title.textContent = t.title;
        container.appendChild(title);

        const form = document.createElement('form');
        form.className = 'publish-form';
        form.id = 'publish-form';

        const nameGroup = document.createElement('div');
        nameGroup.className = 'input-group';
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.name = 'name';
        nameInput.className = 'publish-input';
        nameInput.placeholder = t.companyName;
        nameInput.required = true;
        nameInput.maxLength = 100;
        nameGroup.appendChild(nameInput);
        form.appendChild(nameGroup);

        const emailGroup = document.createElement('div');
        emailGroup.className = 'input-group';
        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.name = 'email';
        emailInput.className = 'publish-input';
        emailInput.placeholder = t.email;
        emailInput.required = true;
        emailGroup.appendChild(emailInput);
        form.appendChild(emailGroup);

        const phoneGroup = document.createElement('div');
        phoneGroup.className = 'input-group';
        const phoneInput = document.createElement('input');
        phoneInput.type = 'tel';
        phoneInput.name = 'phone';
        phoneInput.className = 'publish-input';
        phoneInput.placeholder = t.phone;
        phoneInput.required = true;
        phoneGroup.appendChild(phoneInput);
        form.appendChild(phoneGroup);

        const addressGroup = document.createElement('div');
        addressGroup.className = 'input-group';
        const addressInput = document.createElement('input');
        addressInput.type = 'text';
        addressInput.name = 'address';
        addressInput.className = 'publish-input';
        addressInput.placeholder = t.address;
        addressInput.required = true;
        addressInput.maxLength = 200;
        addressGroup.appendChild(addressInput);
        form.appendChild(addressGroup);

        const communeDropdown = createFilterableDropdown(
            'commune',
            communes,
            t.selectCommune,
            t.searchPlaceholder
        );
        form.appendChild(communeDropdown);

        const productDropdown = createFilterableDropdown(
            'product',
            products,
            t.selectProduct,
            t.searchPlaceholder
        );
        form.appendChild(productDropdown);

        const descGroup = document.createElement('div');
        descGroup.className = 'input-group';
        const descTextarea = document.createElement('textarea');
        descTextarea.name = 'description';
        descTextarea.className = 'publish-textarea';
        descTextarea.placeholder = t.description;
        descTextarea.rows = 4;
        descTextarea.maxLength = 500;
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
        fileInput.required = true;
        
        const fileLabel = document.createElement('label');
        fileLabel.htmlFor = 'company-image';
        fileLabel.className = 'file-input-label';
        fileLabel.textContent = t.selectImage;
        
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                fileLabel.textContent = sanitizeText(e.target.files[0].name);
                fileLabel.classList.add('has-file');
            } else {
                fileLabel.textContent = t.selectImage;
                fileLabel.classList.remove('has-file');
            }
        });
        
        fileWrapper.appendChild(fileInput);
        fileWrapper.appendChild(fileLabel);
        imageGroup.appendChild(fileWrapper);
        form.appendChild(imageGroup);

        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.display = 'none';
        errorDiv.style.color = '#ff6b6b';
        errorDiv.style.marginBottom = '1rem';
        form.appendChild(errorDiv);

        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.style.display = 'none';
        successDiv.style.color = '#4CAF50';
        successDiv.style.marginBottom = '1rem';
        form.appendChild(successDiv);

        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'publish-actions';

        const publishButton = document.createElement('button');
        publishButton.type = 'submit';
        publishButton.className = 'publish-button';
        publishButton.textContent = t.publish;

        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.className = 'publish-button secondary';
        cancelButton.textContent = t.cancel;
        cancelButton.addEventListener('click', () => {
            window.location.href = '/front-page/front-page.html';
        });

        buttonGroup.appendChild(publishButton);
        buttonGroup.appendChild(cancelButton);
        form.appendChild(buttonGroup);

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorDiv.style.display = 'none';
            successDiv.style.display = 'none';

            try {
                const communeSelected = communeDropdown.querySelector('.dropdown-selected');
                const productSelected = productDropdown.querySelector('.dropdown-selected');
                
                const communeValue = communeSelected ? communeSelected.dataset.value : '';
                const productValue = productSelected ? productSelected.dataset.value : '';

                if (!communeValue) {
                    throw new Error(t.selectCommune);
                }
                if (!productValue) {
                    throw new Error(t.selectProduct);
                }

                const sanitizedEmail = sanitizeEmail(emailInput.value);
                if (!sanitizedEmail) {
                    throw new Error(t.invalidEmail);
                }

                const sanitizedName = sanitizeText(nameInput.value.trim());
                const sanitizedPhone = sanitizePhone(phoneInput.value);
                const sanitizedAddress = sanitizeText(addressInput.value.trim());
                const sanitizedDescription = sanitizeText(descTextarea.value.trim());

                if (!sanitizedName) {
                    throw new Error(t.requiredField);
                }

                if (!fileInput.files || fileInput.files.length === 0) {
                    throw new Error(t.selectImage);
                }

                const formData = new FormData();
                formData.append('name', sanitizedName);
                formData.append('email', sanitizedEmail);
                formData.append('phone', sanitizedPhone);
                formData.append('address', sanitizedAddress);
                
                // FIXED: Send description based on current language
                if (lang === 'es') {
                    formData.append('description_es', sanitizedDescription);
                } else {
                    formData.append('description_en', sanitizedDescription);
                }
                
                formData.append('commune_name', communeValue);
                formData.append('product_name', productValue);
                formData.append('lang', lang);
                formData.append('image', fileInput.files[0]);

                publishButton.disabled = true;
                publishButton.textContent = t.publishing;

                const csrfToken = getCSRFToken();
                const correlationId = `fe_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 9)}`;
                
                const response = await fetch('/api/v1/companies/', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'X-Correlation-ID': correlationId,
                        ...(csrfToken && { 'X-CSRF-Token': csrfToken })
                    },
                    body: formData
                });

                console.log(`[${correlationId}] API Request: POST /api/v1/companies/`);
                console.log(`[${correlationId}] Response: ${response.status} ${response.statusText}`);

                if (response.ok) {
                    successDiv.textContent = t.success;
                    successDiv.style.display = 'block';
                    
                    setTimeout(() => {
                        window.location.href = '/profile-view/profile-view.html';
                    }, 2000);
                } else {
                    const error = await response.json();
                    throw new Error(error.detail || t.error);
                }

            } catch (error) {
                console.error('Publish error:', error);
                errorDiv.textContent = sanitizeText(error.message) || t.error;
                errorDiv.style.display = 'block';
                publishButton.disabled = false;
                publishButton.textContent = t.publish;
            }
        });

        container.appendChild(form);
        publishSection.appendChild(container);
    }

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.filterable-dropdown')) {
            document.querySelectorAll('.dropdown-options').forEach(opt => {
                opt.style.display = 'none';
            });
            document.querySelectorAll('.input-group').forEach(grp => {
                grp.classList.remove('dropdown-open');
            });
        }
    });

    await renderPublishForm();

    document.addEventListener('stateChange', renderPublishForm);
});