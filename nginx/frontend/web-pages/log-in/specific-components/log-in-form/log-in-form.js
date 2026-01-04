import {
    getLanguage,
    getLoginState,
    getCompanyPublishState,
    setCompanyPublishState,
    setCompanyData,
    fetchProducts,
    fetchCommunes,
    apiRequest
} from '../../../0-shared-components/utils/shared-functions.js';

document.addEventListener('DOMContentLoaded', () => {
    const publishSection = document.getElementById('publish-section');

    const translations = { /* SAME TRANSLATIONS OBJECT – UNCHANGED */ };

    const clear = () => (publishSection.textContent = '');

    function el(tag, props = {}, ...children) {
        const e = document.createElement(tag);
        Object.assign(e, props);
        children.forEach(c =>
            e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c)
        );
        return e;
    }

    function createDropdown(options, placeholder, id) {
        const root = el('div', { className: 'filterable-dropdown', dataset: { dropdownId: id } });

        const selected = el('div', { className: 'dropdown-selected', dataset: { value: '' } }, placeholder, ' ▼');
        const panel = el('div', { className: 'dropdown-options', style: 'display:none' });
        const search = el('input', { type: 'text', className: 'dropdown-search', placeholder });

        const list = el('div', { className: 'options-list' });

        options.forEach(opt => {
            const item = el('div', { className: 'dropdown-option' }, opt);
            item.dataset.value = opt;
            item.onclick = () => {
                selected.textContent = `${opt} ▼`;
                selected.dataset.value = opt;
                panel.style.display = 'none';
            };
            list.appendChild(item);
        });

        search.oninput = () => {
            const q = search.value.toLowerCase();
            [...list.children].forEach(c =>
                c.style.display = c.textContent.toLowerCase().includes(q) ? 'block' : 'none'
            );
        };

        selected.onclick = e => {
            e.stopPropagation();
            panel.style.display = panel.style.display === 'block' ? 'none' : 'block';
            search.focus();
        };

        panel.append(search, list);
        root.append(selected, panel);
        return root;
    }

    function renderLoginRequired(t) {
        clear();
        publishSection.append(
            el('div', { className: 'publish-container' },
                el('h2', {}, t.title),
                el('p', {}, t.loginRequired),
                el('a', { href: '../log-in/log-in.html' }, t.loginHere)
            )
        );
    }

    function renderAlreadyPublished(t) {
        clear();
        const btn = el('button', { className: 'publish-button' }, t.viewProfile);
        btn.onclick = () => location.href = '../profile-view/profile-view.html';

        publishSection.append(
            el('div', { className: 'publish-container' },
                el('h2', {}, t.alreadyPublished),
                el('p', {}, t.alreadyPublishedMessage),
                btn
            )
        );
    }

    async function renderPublishForm(t, lang) {
        clear();
        publishSection.append(el('p', {}, t.loading));

        const [products, communes] = await Promise.all([fetchProducts(), fetchCommunes()]);

        clear();

        const form = el('form', { className: 'publish-form' });

        const name = el('input', { placeholder: t.companyName, required: true });
        const desc = el('textarea', { placeholder: t.productDescription, required: true });
        const addr = el('input', { placeholder: t.address, required: true });
        const phone = el('input', { placeholder: t.phone, required: true });
        const email = el('input', { type: 'email', placeholder: t.companyEmail, required: true });
        const img = el('input', { type: 'file', accept: 'image/*', required: true });

        const productNames = products.map(p => lang === 'es' ? p.name_es : p.name_en);
        const communeNames = communes.map(c => c.name);

        const productDD = createDropdown(productNames, t.productType, 'product');
        const communeDD = createDropdown(communeNames, t.commune, 'commune');

        const submit = el('button', { type: 'submit' }, t.publishButton);

        form.append(name, desc, addr, phone, email, img, communeDD, productDD, submit);

        form.onsubmit = async e => {
            e.preventDefault();

            const prodVal = productDD.querySelector('.dropdown-selected').dataset.value;
            const comVal = communeDD.querySelector('.dropdown-selected').dataset.value;

            if (!prodVal || !comVal || !img.files[0]) {
                alert(t.imageRequired);
                return;
            }

            const prod = products.find(p => (lang === 'es' ? p.name_es : p.name_en) === prodVal);
            const com = communes.find(c => c.name === comVal);

            const fd = new FormData();
            fd.append('name', name.value);
            fd.append('product_uuid', prod.uuid);
            fd.append('commune_uuid', com.uuid);
            fd.append('address', addr.value);
            fd.append('phone', phone.value);
            fd.append('email', email.value);
            fd.append('image', img.files[0]);
            fd.append(lang === 'es' ? 'description_es' : 'description_en', desc.value);

            const res = await apiRequest('/api/v1/companies/', { method: 'POST', body: fd });
            if (!res.ok) throw new Error();

            const company = await res.json();
            setCompanyData(company);
            setCompanyPublishState(true);
            location.href = '../profile-view/profile-view.html';
        };

        publishSection.append(el('div', { className: 'publish-container' },
            el('h2', {}, t.title),
            form
        ));
    }

    async function render() {
        const lang = getLanguage();
        const t = translations[lang];

        if (!getLoginState()) return renderLoginRequired(t);
        if (getCompanyPublishState()) return renderAlreadyPublished(t);
        await renderPublishForm(t, lang);
    }

    document.addEventListener('languageChange', render);
    document.addEventListener('userHasLogged', render);
    document.addEventListener('companyPublishStateChange', render);
    render();
});
