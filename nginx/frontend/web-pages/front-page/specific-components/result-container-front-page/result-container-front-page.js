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
            previous: 'Anterior',
            next: 'Siguiente'
        },
        en: {
            noResults: 'No results found',
            loading: 'Loading...',
            error: 'Error loading results',
            page: 'Page',
            previous: 'Previous',
            next: 'Next'
        }
    };

    let currentPage = 1;
    let totalResults = 0;
    const resultsPerPage = 20;

    function showLoading() {
        const lang = getLanguage();
        const t = translations[lang];
        clearElement(resultsContainer);
        
        const loading = document.createElement('div');
        loading.className = 'loading-message';
        loading.style.textAlign = 'center';
        loading.style.padding = '2rem';
        loading.style.color = '#666';
        loading.textContent = t.loading;
        resultsContainer.appendChild(loading);
    }

    function showError() {
        const lang = getLanguage();
        const t = translations[lang];
        clearElement(resultsContainer);
        
        const error = document.createElement('div');
        error.className = 'error-message';
        error.style.textAlign = 'center';
        error.style.padding = '2rem';
        error.style.color = '#dc3545';
        error.textContent = t.error;
        resultsContainer.appendChild(error);
    }

    function showNoResults() {
        const lang = getLanguage();
        const t = translations[lang];
        clearElement(resultsContainer);
        
        const noResults = document.createElement('div');
        noResults.className = 'no-results-message';
        noResults.style.textAlign = 'center';
        noResults.style.padding = '2rem';
        noResults.style.color = '#666';
        noResults.textContent = t.noResults;
        resultsContainer.appendChild(noResults);
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
            
            // Sanitize all API response data
            const companies = sanitizeAPIResponse(rawData);
            totalResults = companies.length;

            displayResults(companies, page);

        } catch (error) {
            console.error('Search error:', error);
            showError();
        }
    }

    function displayResults(companies, page) {
        const lang = getLanguage();

        clearElement(resultsContainer);

        if (!companies || companies.length === 0) {
            showNoResults();
            return;
        }

        // Create grid container
        const grid = document.createElement('div');
        grid.className = 'results-grid';

        companies.forEach(company => {
            // buildBusinessCard handles all sanitization internally
            const card = buildBusinessCard(company, lang);
            grid.appendChild(card);
        });

        resultsContainer.appendChild(grid);

        // Always show pagination if we have results
        createPagination(page, companies.length);
    }

    function createPagination(page, resultCount) {
        const lang = getLanguage();
        const t = translations[lang];

        const paginationContainer = document.createElement('div');
        paginationContainer.className = 'pagination-container';

        // Previous button
        if (page > 1) {
            const prevLink = document.createElement('a');
            prevLink.href = '#';
            prevLink.className = 'page-link';
            prevLink.textContent = t.previous;
            prevLink.addEventListener('click', (e) => {
                e.preventDefault();
                performSearch(page - 1);
            });
            paginationContainer.appendChild(prevLink);
        }

        // Current page indicator
        const pageInfo = document.createElement('span');
        pageInfo.className = 'page-link active';
        pageInfo.textContent = `${t.page} ${page}`;
        paginationContainer.appendChild(pageInfo);

        // Next button - show if we got a full page of results
        if (resultCount === resultsPerPage) {
            const nextLink = document.createElement('a');
            nextLink.href = '#';
            nextLink.className = 'page-link';
            nextLink.textContent = t.next;
            nextLink.addEventListener('click', (e) => {
                e.preventDefault();
                performSearch(page + 1);
            });
            paginationContainer.appendChild(nextLink);
        }

        resultsContainer.appendChild(paginationContainer);
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

    // Listen for search trigger
    document.addEventListener('searchTriggered', () => {
        performSearch(1);
    });

    // Re-render on language change
    document.addEventListener('stateChange', () => {
        performSearch(currentPage);
    });

    // Initial load - show all companies
    performSearch(1);
});
