import {
    getLanguage,
    apiRequest,
    fetchProducts,
    fetchCommunes
} from '../../../0-shared-components/utils/shared-functions.js';

//  ADDED: Import all necessary sanitizer functions
import {
    sanitizeText,
    sanitizeEmail,
    sanitizePhone,
    sanitizeURL,
    sanitizeAPIResponse,
    validateFormData
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', async () => {
    const publishContainer = document.getElementById('publish-section-container');

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
            website: 'Sitio Web (opcional)',
            publish: 'Publicar',
            cancel: 'Cancelar',
            selectCommune: 'Seleccionar Comuna',
            selectProduct: 'Seleccionar Producto',
            loading: 'Cargando...',
            publishing: 'Publicando...',
            success: '¡Empresa publicada exitosamente!',
            error: 'Error al publicar la empresa',
            alreadyPublished: 'Ya tienes una empresa publicada'
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
            website: 'Website (optional)',
            publish: 'Publish',
            cancel: 'Cancel',
            selectCommune: 'Select Commune',
            selectProduct: 'Select Product',
            loading: 'Loading...',
            publishing: 'Publishing...',
            success: 'Company published successfully!',
            error: 'Error publishing company',
            alreadyPublished: 'You already have a published company'
        }
    };

    async function checkExistingCompany() {
        try {
            const response = await apiRequest('/api/v1/companies/user/my-company');
            if (response.ok) {
                return true; // Company exists
            }
            return false;
        } catch (error) {
            return false;
        }
    }

    async function renderPublishForm() {
        const lang = getLanguage();
        const t = translations[lang];

        publishContainer.innerHTML = `<div class="loading">${t.loading}</div>`;

        // Check if user already has a company
        const hasCompany = await checkExistingCompany();
        if (hasCompany) {
            publishContainer.innerHTML = `
                <div class="info-message">
                    <p>${t.alreadyPublished}</p>
                    <a href="/profile-view" class="btn-primary">Ver Mi Empresa</a>
                </div>
            `;
            return;
        }

        //  CRITICAL FIX: Sanitize API responses
        const rawProducts = await fetchProducts();
        const rawCommunes = await fetchCommunes();
        const products = sanitizeAPIResponse(rawProducts);
        const communes = sanitizeAPIResponse(rawCommunes);

        publishContainer.innerHTML = '';

        const form = document.createElement('form');
        form.className = 'publish-form';
        form.id = 'publish-form';

        const title = document.createElement('h2');
        title.textContent = t.title;
        form.appendChild(title);

        // Company name
        const nameGroup = document.createElement('div');
        nameGroup.className = 'form-group';
        const nameLabel = document.createElement('label');
        nameLabel.textContent = t.companyName + ' *';
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.name = 'name';
        nameInput.required = true;
        nameGroup.appendChild(nameLabel);
        nameGroup.appendChild(nameInput);
        form.appendChild(nameGroup);

        // Email
        const emailGroup = document.createElement('div');
        emailGroup.className = 'form-group';
        const emailLabel = document.createElement('label');
        emailLabel.textContent = t.email + ' *';
        const emailInput = document.createElement('input');
        emailInput.type = 'email';
        emailInput.name = 'email';
        emailInput.required = true;
        emailGroup.appendChild(emailLabel);
        emailGroup.appendChild(emailInput);
        form.appendChild(emailGroup);

        // Phone
        const phoneGroup = document.createElement('div');
        phoneGroup.className = 'form-group';
        const phoneLabel = document.createElement('label');
        phoneLabel.textContent = t.phone + ' *';
        const phoneInput = document.createElement('input');
        phoneInput.type = 'tel';
        phoneInput.name = 'phone';
        phoneInput.required = true;
        phoneGroup.appendChild(phoneLabel);
        phoneGroup.appendChild(phoneInput);
        form.appendChild(phoneGroup);

        // Address
        const addressGroup = document.createElement('div');
        addressGroup.className = 'form-group';
        const addressLabel = document.createElement('label');
        addressLabel.textContent = t.address + ' *';
        const addressInput = document.createElement('input');
        addressInput.type = 'text';
        addressInput.name = 'address';
        addressInput.required = true;
        addressGroup.appendChild(addressLabel);
        addressGroup.appendChild(addressInput);
        form.appendChild(addressGroup);

        // Commune dropdown
        const communeGroup = document.createElement('div');
        communeGroup.className = 'form-group';
        const communeLabel = document.createElement('label');
        communeLabel.textContent = t.commune + ' *';
        const communeSelect = document.createElement('select');
        communeSelect.name = 'commune_id';
        communeSelect.required = true;

        const communeDefault = document.createElement('option');
        communeDefault.value = '';
        communeDefault.textContent = t.selectCommune;
        communeSelect.appendChild(communeDefault);

        //  FIXED: Data already sanitized
        communes.forEach(commune => {
            const option = document.createElement('option');
            option.value = commune.id;
            option.textContent = commune.name;
            communeSelect.appendChild(option);
        });

        communeGroup.appendChild(communeLabel);
        communeGroup.appendChild(communeSelect);
        form.appendChild(communeGroup);

        // Product dropdown
        const productGroup = document.createElement('div');
        productGroup.className = 'form-group';
        const productLabel = document.createElement('label');
        productLabel.textContent = t.product + ' *';
        const productSelect = document.createElement('select');
        productSelect.name = 'product_id';
        productSelect.required = true;

        const productDefault = document.createElement('option');
        productDefault.value = '';
        productDefault.textContent = t.selectProduct;
        productSelect.appendChild(productDefault);

        //  FIXED: Data already sanitized
        products.forEach(product => {
            const option = document.createElement('option');
            option.value = product.id;
            option.textContent = product.name;
            productSelect.appendChild(option);
        });

        productGroup.appendChild(productLabel);
        productGroup.appendChild(productSelect);
        form.appendChild(productGroup);

        // Description
        const descGroup = document.createElement('div');
        descGroup.className = 'form-group';
        const descLabel = document.createElement('label');
        descLabel.textContent = t.description;
        const descTextarea = document.createElement('textarea');
        descTextarea.name = 'description';
        descTextarea.rows = 4;
        descGroup.appendChild(descLabel);
        descGroup.appendChild(descTextarea);
        form.appendChild(descGroup);

        // Website
        const websiteGroup = document.createElement('div');
        websiteGroup.className = 'form-group';
        const websiteLabel = document.createElement('label');
        websiteLabel.textContent = t.website;
        const websiteInput = document.createElement('input');
        websiteInput.type = 'url';
        websiteInput.name = 'website';
        websiteGroup.appendChild(websiteLabel);
        websiteGroup.appendChild(websiteInput);
        form.appendChild(websiteGroup);

        // Error message container
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.display = 'none';
        form.appendChild(errorDiv);

        // Buttons
        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'form-buttons';

        const publishButton = document.createElement('button');
        publishButton.type = 'submit';
        publishButton.className = 'btn-primary';
        publishButton.textContent = t.publish;

        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.className = 'btn-secondary';
        cancelButton.textContent = t.cancel;
        cancelButton.addEventListener('click', () => {
            window.location.href = '/';
        });

        buttonGroup.appendChild(publishButton);
        buttonGroup.appendChild(cancelButton);
        form.appendChild(buttonGroup);

        //  CRITICAL FIX: Validate and sanitize all form data
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorDiv.style.display = 'none';

            try {
                const formData = new FormData(form);
                
                //  Validate and sanitize all inputs
                const validatedData = validateFormData({
                    name: formData.get('name'),
                    contact_email: formData.get('email'),
                    contact_phone: formData.get('phone'),
                    address: formData.get('address'),
                    description: formData.get('description') || '',
                    website: formData.get('website') || '',
                    commune_id: parseInt(formData.get('commune_id')),
                    product_id: parseInt(formData.get('product_id'))
                });

                // Additional validation
                if (!validatedData.commune_id || validatedData.commune_id === 0) {
                    throw new Error(t.selectCommune);
                }
                if (!validatedData.product_id || validatedData.product_id === 0) {
                    throw new Error(t.selectProduct);
                }

                publishButton.disabled = true;
                publishButton.textContent = t.publishing;

                const response = await apiRequest('/api/v1/companies', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(validatedData)
                });

                if (response.ok) {
                    alert(t.success);
                    window.location.href = '/profile-view';
                } else {
                    const error = await response.json();
                    throw new Error(error.error || t.error);
                }

            } catch (error) {
                console.error('Publish error:', error);
                errorDiv.textContent = error.message || t.error;
                errorDiv.style.display = 'block';
                publishButton.disabled = false;
                publishButton.textContent = t.publish;
            }
        });

        publishContainer.appendChild(form);
    }

    await renderPublishForm();

    document.addEventListener('languageChange', renderPublishForm);
});