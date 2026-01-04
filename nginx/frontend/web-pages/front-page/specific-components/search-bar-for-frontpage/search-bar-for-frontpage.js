import {
    getLanguage,
    fetchProducts,
    fetchCommunes,
    sanitizeText,
    sanitizeAPIResponse  //  ADDED
} from '../../../0-shared-components/utils/shared-functions.js';

document.addEventListener('DOMContentLoaded', async () => {
    const searchContainer = document.getElementById('search-bar-container');

    const translations = {
        es: {
            placeholder: 'Buscar empresas...',
            searchButton: 'Buscar',
            commune: 'Comuna',
            product: 'Producto',
            allCommunes: 'Todas Las Comunas',
            allProducts: 'Todos Los Productos'
        },
        en: {
            placeholder: 'Search companies...',
            searchButton: 'Search',
            commune: 'Commune',
            product: 'Product',
            allCommunes: 'All Communes',
            allProducts: 'All Products'
        }
    };

    async function renderSearchBar() {
        const lang = getLanguage();
        const t = translations[lang];

        //  CRITICAL FIX: Sanitize API responses
        const rawProducts = await fetchProducts();
        const rawCommunes = await fetchCommunes();
        
        const products = sanitizeAPIResponse(rawProducts);
        const communes = sanitizeAPIResponse(rawCommunes);

        searchContainer.innerHTML = '';

        const searchBar = document.createElement('div');
        searchBar.className = 'search-bar';

        // Search input
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.id = 'search-query';
        searchInput.className = 'search-input';
        searchInput.placeholder = t.placeholder;

        // Commune dropdown
        const communeDropdown = createDropdown('commune', t.commune, communes, t.allCommunes);

        // Product dropdown
        const productDropdown = createDropdown('product', t.product, products, t.allProducts);

        // Search button
        const searchButton = document.createElement('button');
        searchButton.className = 'search-button';
        searchButton.textContent = t.searchButton;
        searchButton.addEventListener('click', triggerSearch);

        searchBar.appendChild(searchInput);
        searchBar.appendChild(communeDropdown);
        searchBar.appendChild(productDropdown);
        searchBar.appendChild(searchButton);

        searchContainer.appendChild(searchBar);

        // Enter key support
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                triggerSearch();
            }
        });
    }

    function createDropdown(id, label, options, defaultText) {
        const container = document.createElement('div');
        container.className = 'dropdown-container';
        container.dataset.dropdownId = id;

        const selected = document.createElement('div');
        selected.className = 'dropdown-selected';
        selected.textContent = defaultText;
        selected.dataset.value = '';

        const optionsList = document.createElement('div');
        optionsList.className = 'dropdown-options';

        // Default option
        const defaultOption = document.createElement('div');
        defaultOption.className = 'dropdown-option';
        defaultOption.textContent = defaultText;
        defaultOption.dataset.value = '';
        defaultOption.addEventListener('click', () => {
            selected.textContent = defaultText;
            selected.dataset.value = '';
            optionsList.classList.remove('show');
        });
        optionsList.appendChild(defaultOption);

        //  FIXED: Data already sanitized above
        options.forEach(option => {
            const optionElement = document.createElement('div');
            optionElement.className = 'dropdown-option';
            optionElement.textContent = option.name || option;
            optionElement.dataset.value = option.id || option;
            
            optionElement.addEventListener('click', () => {
                selected.textContent = option.name || option;
                selected.dataset.value = option.id || option;
                optionsList.classList.remove('show');
            });
            
            optionsList.appendChild(optionElement);
        });

        selected.addEventListener('click', () => {
            optionsList.classList.toggle('show');
        });

        container.appendChild(selected);
        container.appendChild(optionsList);

        return container;
    }

    function triggerSearch() {
        const event = new CustomEvent('searchTriggered');
        document.dispatchEvent(event);
    }

    await renderSearchBar();

    document.addEventListener('languageChange', renderSearchBar);
});