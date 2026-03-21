import {
    getLanguage,
    apiRequest
} from '../../../0-shared-components/utils/shared-functions.js';

import {
    sanitizeAPIResponse,
    buildBusinessCard,
    clearElement
} from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const resultsContainer = document.getElementById('results-container');

    const translations = {
        es: {
            noResults: 'No se encontraron resultados',
            loading: 'Cargando...',
            error: 'Error al cargar los resultados',
            page: 'Página',
            previous: '← Anterior',
            next: 'Siguiente →'
        },
        en: {
            noResults: 'No results found',
            loading: 'Loading...',
            error: 'Error loading results',
            page: 'Page',
            previous: '← Previous',
            next: 'Next →'
        }
    };

    let currentPage = 1;
    let lastResultCount = 0;
    const resultsPerPage = 4;

    function getOrCreateContentArea() {
        let contentArea = resultsContainer.querySelector('.results-content-area');
        if (!contentArea) {
            contentArea = document.createElement('div');
            contentArea.className = 'results-content-area';
            resultsContainer.insertBefore(contentArea, resultsContainer.firstChild);
        }
        return contentArea;
    }

    function showLoading() {
        const lang = getLanguage();
        const contentArea = getOrCreateContentArea();
        clearElement(contentArea);

        const loading = document.createElement('div');
        // .loading-message already defines text-align, padding, color in the CSS
        loading.className = 'loading-message';
        loading.textContent = translations[lang].loading;
        contentArea.appendChild(loading);
    }

    function showError() {
        const lang = getLanguage();
        const contentArea = getOrCreateContentArea();
        clearElement(contentArea);

        const error = document.createElement('div');
        // .error-message already defines text-align, padding, color in the CSS
        error.className = 'error-message';
        error.textContent = translations[lang].error;
        contentArea.appendChild(error);
    }

    function showNoResults() {
        const lang = getLanguage();
        const contentArea = getOrCreateContentArea();
        clearElement(contentArea);

        const noResults = document.createElement('div');
        // .no-results-message already defines text-align, padding, color in the CSS
        noResults.className = 'no-results-message';
        noResults.textContent = translations[lang].noResults;
        contentArea.appendChild(noResults);
    }

    async function fetchResults(query, commune, product, page = 1) {
        try {
            showLoading();

            const params = new URLSearchParams({
                lang: getLanguage(),
                limit: resultsPerPage.toString(),
                offset: ((page - 1) * resultsPerPage).toString()
            });

            if (query && query.trim()) {
                params.append('q', query.trim());
            }
            if (commune && commune !== 'Todas Las Comunas' && commune !== 'All Communes') {
                params.append('commune', commune);
            }
            if (product && product !== 'Todos Los Productos' && product !== 'All Products') {
                params.append('product', product);
            }

            const response = await apiRequest(`/api/v1/companies/search?${params}`);

            if (!response.ok) {
                throw new Error('Search failed');
            }

            const rawData = await response.json();
            const companies = sanitizeAPIResponse(rawData);

            lastResultCount = companies.length;

            displayResults(companies, page);

        } catch (error) {
            console.error('Search error:', error);
            showError();
            updatePagination(currentPage);
        }
    }

    function displayResults(companies, page) {
        const lang = getLanguage();
        const contentArea = getOrCreateContentArea();
        clearElement(contentArea);

        if (!companies || companies.length === 0) {
            showNoResults();
        } else {
            const grid = document.createElement('div');
            grid.className = 'results-grid';

            companies.forEach(company => {
                const card = buildBusinessCard(company, lang);
                grid.appendChild(card);
            });

            contentArea.appendChild(grid);
        }

        updatePagination(page);
    }

    function updatePagination(page) {
        const lang = getLanguage();
        const t = translations[lang];

        let paginationContainer = resultsContainer.querySelector('.pagination-container');

        if (!paginationContainer) {
            paginationContainer = document.createElement('div');
            paginationContainer.className = 'pagination-container';
            resultsContainer.appendChild(paginationContainer);
        }

        clearElement(paginationContainer);

        const prevLink = document.createElement('a');
        prevLink.href = '#';
        prevLink.className = page <= 1
            ? 'page-link disabled'
            : 'page-link';
        prevLink.textContent = t.previous;

        if (page > 1) {
            prevLink.addEventListener('click', (e) => {
                e.preventDefault();
                performSearch(page - 1);
            });
        }
        paginationContainer.appendChild(prevLink);

        const pageInfo = document.createElement('span');
        pageInfo.className = 'page-link active';
        pageInfo.textContent = `${t.page} ${page}`;
        paginationContainer.appendChild(pageInfo);

        const nextLink = document.createElement('a');
        nextLink.href = '#';
        nextLink.className = lastResultCount < resultsPerPage
            ? 'page-link disabled'
            : 'page-link';
        nextLink.textContent = t.next;

        if (lastResultCount >= resultsPerPage) {
            nextLink.addEventListener('click', (e) => {
                e.preventDefault();
                performSearch(page + 1);
            });
        }
        paginationContainer.appendChild(nextLink);
    }

    function performSearch(page = 1) {
        currentPage = page;

        const searchInput = document.getElementById('search-query');
        const query = searchInput ? searchInput.value : '';

        const communeDropdown = document.querySelector('[data-dropdown-id="commune"] .dropdown-selected');
        const commune = communeDropdown ? communeDropdown.dataset.value : '';

        const productDropdown = document.querySelector('[data-dropdown-id="product"] .dropdown-selected');
        const product = productDropdown ? productDropdown.dataset.value : '';

        fetchResults(query, commune, product, page);
    }

    document.addEventListener('searchTriggered', () => {
        performSearch(1);
    });

    document.addEventListener('stateChange', () => {
        performSearch(currentPage);
    });

    performSearch(1);
});