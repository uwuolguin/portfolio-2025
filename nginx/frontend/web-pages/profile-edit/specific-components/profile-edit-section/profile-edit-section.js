import {
    getLanguage,
    apiRequest,
    fetchProducts,
    fetchCommunes
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeText,
    sanitizeURL,
    sanitizeEmail,
    sanitizePhone,
    sanitizeAPIResponse,
    validateFormData  //  ADDED
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', async () => {
    const editContainer = document.getElementById('profile-edit-container');

    const translations = {
        es: {
            editProfile: 'Editar Perfil',
            editCompany: 'Editar Empresa',
            name: 'Nombre',
            email: 'Correo',
            phone: 'Teléfono',
            address: 'Dirección',
            commune: 'Comuna',
            product: 'Producto',
            description: 'Descripción',
            website: 'Sitio Web',
            save: 'Guardar',
            cancel: 'Cancelar',
            loading: 'Cargando...',
            saving: 'Guardando...',
            success: 'Cambios guardados exitosamente',
            error: 'Error al guardar los cambios',
            selectCommune: 'Seleccionar Comuna',
            selectProduct: 'Seleccionar Producto'
        },
        en: {
            editProfile: 'Edit Profile',
            editCompany: 'Edit Company',
            name: 'Name',
            email: 'Email',
            phone: 'Phone',
            address: 'Address',
            commune: 'Commune',
            product: 'Product',
            description: 'Description',
            website: 'Website',
            save: 'Save',
            cancel: 'Cancel',
            loading: 'Loading...',
            saving: 'Saving...',
            success: 'Changes saved successfully',
            error: 'Error saving changes',
            selectCommune: 'Select Commune',
            selectProduct: 'Select Product'
        }
    };

    //  CRITICAL FIX: Sanitize API response
    async function fetchMyCompany() {
        try {
            const response = await apiRequest('/api/v1/companies/user/my-company');
            const rawData = await response.json();
            return sanitizeAPIResponse(rawData);
        } catch (error) {
            console.error('Error fetching company:', error);
            return null;
        }
    }

    async function renderEditForm() {
        const lang = getLanguage();
        const t = translations[lang];

        editContainer.innerHTML = `<div class="loading">${t.loading}</div>`;

        const companyData = await fetchMyCompany();
        
        //  CRITICAL FIX: Sanitize dropdown data
        const rawProducts = await fetchProducts();
        const rawCommunes = await fetchCommunes();
        const products = sanitizeAPIResponse(rawProducts);
        const communes = sanitizeAPIResponse(rawCommunes);

        editContainer.innerHTML = '';

        const form = document.createElement('form');
        form.className = 'edit-form';
        form.id = 'company-edit-form';

        const title = document.createElement('h2');
        title.textContent = t.editCompany;
        form.appendChild(title);

        //  FIXED: Data already sanitized
        const fields = [
            { name: 'name', label: t.name, type: 'text', value: companyData?.name || '', required: true },
            { name: 'email', label: t.email, type: 'email', value: companyData?.contact_email || '', required: true },
            { name: 'phone', label: t.phone, type: 'tel', value: companyData?.contact_phone || '', required: true },
            { name: 'address', label: t.address, type: 'text', value: companyData?.address || '', required: true },
            { name: 'description', label: t.description, type: 'textarea', value: companyData?.description || '', required: false },
            { name: 'website', label: t.website, type: 'url', value: companyData?.website || '', required: false }
        ];

        fields.forEach(field => {
            const fieldGroup = document.createElement('div');
            fieldGroup.className = 'form-group';

            const label = document.createElement('label');
            label.textContent = field.label;
            if (field.required) label.textContent += ' *';

            let input;
            if (field.type === 'textarea') {
                input = document.createElement('textarea');
                input.rows = 4;
            } else {
                input = document.createElement('input');
                input.type = field.type;
            }

            input.name = field.name;
            input.value = field.value;
            input.required = field.required;

            fieldGroup.appendChild(label);
            fieldGroup.appendChild(input);
            form.appendChild(fieldGroup);
        });

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

        communes.forEach(commune => {
            const option = document.createElement('option');
            option.value = commune.id;
            option.textContent = commune.name;
            if (companyData?.commune_id === commune.id) {
                option.selected = true;
            }
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

        products.forEach(product => {
            const option = document.createElement('option');
            option.value = product.id;
            option.textContent = product.name;
            if (companyData?.product_id === product.id) {
                option.selected = true;
            }
            productSelect.appendChild(option);
        });

        productGroup.appendChild(productLabel);
        productGroup.appendChild(productSelect);
        form.appendChild(productGroup);

        // Buttons
        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'form-buttons';

        const saveButton = document.createElement('button');
        saveButton.type = 'submit';
        saveButton.className = 'btn-primary';
        saveButton.textContent = t.save;

        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.className = 'btn-secondary';
        cancelButton.textContent = t.cancel;
        cancelButton.addEventListener('click', () => {
            window.location.href = '/profile-view';
        });

        buttonGroup.appendChild(saveButton);
        buttonGroup.appendChild(cancelButton);
        form.appendChild(buttonGroup);

        //  CRITICAL FIX: Validate form data before submission
        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            const formData = new FormData(form);
            const data = Object.fromEntries(formData);

            try {
                //  Validate and sanitize all form data
                const validatedData = validateFormData({
                    name: data.name,
                    contact_email: data.email,
                    contact_phone: data.phone,
                    address: data.address,
                    description: data.description,
                    website: data.website,
                    commune_id: parseInt(data.commune_id),
                    product_id: parseInt(data.product_id)
                });

                saveButton.disabled = true;
                saveButton.textContent = t.saving;

                const response = await apiRequest(`/api/v1/companies/${companyData.id}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(validatedData)
                });

                if (response.ok) {
                    alert(t.success);
                    window.location.href = '/profile-view';
                } else {
                    throw new Error('Update failed');
                }

            } catch (error) {
                console.error('Save error:', error);
                alert(error.message || t.error);
                saveButton.disabled = false;
                saveButton.textContent = t.save;
            }
        });

        editContainer.appendChild(form);
    }

    await renderEditForm();

    document.addEventListener('languageChange', renderEditForm);
});