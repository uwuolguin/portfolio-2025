import {
    getLanguage,
    apiRequest,
    fetchProducts,
    fetchCommunes,
    getCSRFToken
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeText,
    sanitizeEmail,
    sanitizePhone,
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
            selectRequired: 'Por favor selecciona una opción',
            notVerifiedTitle: 'Cuenta no verificada',
            notVerifiedMessage: 'Debes verificar tu correo electrónico para publicar tu empresa. Por favor revisa tu bandeja de entrada y haz clic en el enlace de verificación, luego inicia sesión nuevamente.',
            resendLabel: '¿No recibiste el correo de verificación?',
            resendButton: 'Reenviar correo',
            resendSent: 'Correo de verificación enviado. Revisa tu bandeja de entrada.',
            resendError: 'Error al reenviar el correo. Intenta nuevamente.',
            sending: 'Enviando...'
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
            selectRequired: 'Please select an option',
            notVerifiedTitle: 'Account not verified',
            notVerifiedMessage: 'You must verify your email to publish your company. Please check your inbox and click the verification link, then log in again.',
            resendLabel: 'Didn\'t receive the verification email?',
            resendButton: 'Resend email',
            resendSent: 'Verification email sent. Please check your inbox.',
            resendError: 'Failed to resend email. Please try again.',
            sending: 'Sending...'
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

    async function fetchCurrentUser() {
        try {
            const response = await apiRequest('/api/v1/users/me');
            if (response.ok) return await response.json();
            return null;
        } catch {
            return null;
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
            if (lang !== 'es' && lang !== 'en') {
                throw new Error(`Language must be 'es' or 'en', got: "${lang}"`);
            }

            const displayName =
                lang === 'es'
                    ? (option.name_es || option.name)
                    : (option.name_en || option.name);

            const value =
                lang === 'es'
                    ? (option.name_es || option.name)
                    : (option.name_en || option.name);

            if (!displayName || !value) {
                throw new Error(`Missing ${lang} translation for option: ${JSON.stringify(option)}`);
            }

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

        searchInput.addEventListener('click', (e) => e.stopPropagation());

        selected.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = optionsContainer.style.display === 'block';
            document.querySelectorAll('.dropdown-options').forEach(opt => opt.style.display = 'none');
            document.querySelectorAll('.input-group').forEach(grp => grp.classList.remove('dropdown-open'));
            if (!isOpen) {
                optionsContainer.style.display = 'block';
                container.classList.add('dropdown-open');
                searchInput.value = '';
                searchInput.focus();
                optionsList.querySelectorAll('.dropdown-option').forEach(opt => opt.style.display = 'block');
            }
        });

        dropdownWrapper.appendChild(selected);
        dropdownWrapper.appendChild(optionsContainer);
        container.appendChild(dropdownWrapper);

        return container;
    }

    async function renderPublishForm() {
        const lang = getLanguage();
        const t = translations[lang];

        // ── GATE 1: no session ─────────────────────────────────────────────
        const currentUser = await fetchCurrentUser();

        if (!currentUser) {
            clearElement(publishSection);

            const container = document.createElement('div');
            container.className = 'publish-container';

            const title = document.createElement('h2');
            title.className = 'publish-title';
            title.textContent = t.title;
            container.appendChild(title);

            const message = document.createElement('p');
            message.className = 'login-message text-white mb-md';
            message.textContent = t.loginRequired;
            container.appendChild(message);

            const loginLink = document.createElement('a');
            loginLink.href = '/log-in/log-in.html';
            loginLink.className = 'publish-button no-decoration visible-inline';
            loginLink.textContent = t.loginHere;
            container.appendChild(loginLink);

            const signupSection = document.createElement('div');
            signupSection.className = 'mt-md text-white';
            const noAccountText = document.createTextNode(t.noAccount + ' ');
            signupSection.appendChild(noAccountText);
            const signupLink = document.createElement('a');
            signupLink.href = '/sign-up/sign-up.html';
            signupLink.className = 'text-orange no-decoration';
            signupLink.textContent = t.registerHere;
            signupSection.appendChild(signupLink);
            container.appendChild(signupSection);

            publishSection.appendChild(container);
            return;
        }

        // ── GATE 2: email not verified ─────────────────────────────────────
        if (!currentUser.email_verified) {
            clearElement(publishSection);

            const container = document.createElement('div');
            container.className = 'publish-container';

            const title = document.createElement('h2');
            title.className = 'publish-title';
            title.textContent = t.notVerifiedTitle;
            container.appendChild(title);

            const message = document.createElement('p');
            message.className = 'text-muted-lt state-msg mb-md';
            message.textContent = t.notVerifiedMessage;
            container.appendChild(message);

            // Feedback div — starts hidden, gets text-success or text-error + visible-block
            const statusDiv = document.createElement('div');
            statusDiv.className = 'hidden state-msg-sm mb-sm';
            container.appendChild(statusDiv);

            const resendSection = document.createElement('div');
            resendSection.className = 'resend-verification-section';

            const resendLabel = document.createElement('p');
            resendLabel.className = 'resend-verification-text';
            resendLabel.textContent = t.resendLabel;
            resendSection.appendChild(resendLabel);

            const resendButton = document.createElement('button');
            resendButton.type = 'button';
            resendButton.className = 'publish-button';
            resendButton.textContent = t.resendButton;

            resendButton.addEventListener('click', async () => {
                resendButton.disabled = true;
                resendButton.textContent = t.sending;

                try {
                    const response = await apiRequest(
                        `/api/v1/users/resend-verification?email=${encodeURIComponent(currentUser.email)}`,
                        { method: 'POST' }
                    );

                    if (response.ok) {
                        statusDiv.classList.add('text-success', 'visible-block');
                        statusDiv.classList.remove('hidden', 'text-error');
                        statusDiv.textContent = t.resendSent;
                        resendSection.classList.add('hidden');
                    } else {
                        const error = await response.json();
                        throw new Error(error.detail || t.resendError);
                    }
                } catch (error) {
                    statusDiv.classList.add('text-error', 'visible-block');
                    statusDiv.classList.remove('hidden', 'text-success');
                    statusDiv.textContent = sanitizeText(error.message) || t.resendError;
                    resendButton.disabled = false;
                    resendButton.textContent = t.resendButton;
                }
            });

            resendSection.appendChild(resendButton);
            container.appendChild(resendSection);
            publishSection.appendChild(container);
            return;
        }

        // ── GATE 3: already has a company ──────────────────────────────────
        const hasCompany = await checkExistingCompany();
        if (hasCompany) {
            clearElement(publishSection);

            const container = document.createElement('div');
            container.className = 'publish-container';

            const title = document.createElement('h2');
            title.className = 'publish-title';
            title.textContent = t.title;
            container.appendChild(title);

            const message = document.createElement('p');
            message.className = 'already-published-message text-white mb-md';
            message.textContent = t.alreadyPublished;
            container.appendChild(message);

            const viewLink = document.createElement('a');
            viewLink.href = '/profile-view/profile-view.html';
            viewLink.className = 'publish-button no-decoration visible-inline';
            viewLink.textContent = t.viewCompany;
            container.appendChild(viewLink);

            publishSection.appendChild(container);
            return;
        }

        // ── GATE 4: show publish form ──────────────────────────────────────
        clearElement(publishSection);

        const container = document.createElement('div');
        container.className = 'publish-container';

        const title = document.createElement('h2');
        title.className = 'publish-title';
        title.textContent = t.title;
        container.appendChild(title);

        const form = document.createElement('form');
        form.className = 'publish-form';

        const products = await fetchProducts();
        const communes = await fetchCommunes();

        const nameGroup = document.createElement('div');
        nameGroup.className = 'input-group';
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.name = 'name';
        nameInput.className = 'publish-input';
        nameInput.placeholder = t.companyName;
        nameInput.maxLength = 100;
        nameInput.required = true;
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
        phoneGroup.appendChild(phoneInput);
        form.appendChild(phoneGroup);

        const addressGroup = document.createElement('div');
        addressGroup.className = 'input-group';
        const addressInput = document.createElement('input');
        addressInput.type = 'text';
        addressInput.name = 'address';
        addressInput.className = 'publish-input';
        addressInput.placeholder = t.address;
        addressGroup.appendChild(addressInput);
        form.appendChild(addressGroup);

        const communeDropdown = createFilterableDropdown('commune', communes, t.selectCommune, t.searchPlaceholder);
        form.appendChild(communeDropdown);

        const productDropdown = createFilterableDropdown('product', products, t.selectProduct, t.searchPlaceholder);
        form.appendChild(productDropdown);

        const descGroup = document.createElement('div');
        descGroup.className = 'input-group';
        const descTextarea = document.createElement('textarea');
        descTextarea.name = 'description';
        descTextarea.className = 'publish-textarea';
        descTextarea.placeholder = t.description;
        descTextarea.rows = 4;
        descTextarea.maxLength = 500;
        descTextarea.required = true;
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

        // Error and success divs — start hidden
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message hidden text-error mb-sm';
        form.appendChild(errorDiv);

        const successDiv = document.createElement('div');
        successDiv.className = 'success-message hidden text-success mb-sm';
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

            // Reset state
            errorDiv.classList.add('hidden');
            successDiv.classList.add('hidden');

            try {
                const communeSelected = communeDropdown.querySelector('.dropdown-selected');
                const productSelected = productDropdown.querySelector('.dropdown-selected');
                const communeValue = communeSelected ? communeSelected.dataset.value : '';
                const productValue = productSelected ? productSelected.dataset.value : '';

                if (!communeValue) throw new Error(t.selectCommune);
                if (!productValue) throw new Error(t.selectProduct);

                const sanitizedEmail = sanitizeEmail(emailInput.value);
                if (!sanitizedEmail) throw new Error(t.invalidEmail);

                const sanitizedName = sanitizeText(nameInput.value.trim());
                const sanitizedPhone = sanitizePhone(phoneInput.value);
                const sanitizedAddress = sanitizeText(addressInput.value.trim());
                const sanitizedDescription = sanitizeText(descTextarea.value.trim());

                if (!sanitizedName) throw new Error(t.requiredField);
                if (!fileInput.files || fileInput.files.length === 0) throw new Error(t.selectImage);

                const formData = new FormData();
                formData.append('name', sanitizedName);
                formData.append('email', sanitizedEmail);
                formData.append('phone', sanitizedPhone);
                formData.append('address', sanitizedAddress);

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

                const response = await fetch('/api/v1/companies', {
                    method: 'POST',
                    credentials: 'include',
                    headers: {
                        'X-Correlation-ID': correlationId,
                        ...(csrfToken && { 'X-CSRF-Token': csrfToken })
                    },
                    body: formData
                });

                if (response.ok) {
                    successDiv.textContent = t.success;
                    successDiv.classList.remove('hidden');
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
                errorDiv.classList.remove('hidden');
                publishButton.disabled = false;
                publishButton.textContent = t.publish;
            }
        });

        container.appendChild(form);
        publishSection.appendChild(container);
    }

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.filterable-dropdown')) {
            document.querySelectorAll('.dropdown-options').forEach(opt => opt.style.display = 'none');
            document.querySelectorAll('.input-group').forEach(grp => grp.classList.remove('dropdown-open'));
        }
    });

    await renderPublishForm();

    document.addEventListener('stateChange', renderPublishForm);
});