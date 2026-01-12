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

    function showLoading() {
        const lang = getLanguage();
        const t = translations[lang];
        
        // Find existing content area or create it
        let contentArea = resultsContainer.querySelector('.results-content-area');
        if (!contentArea) {
            contentArea = document.createElement('div');
            contentArea.className = 'results-content-area';
            resultsContainer.insertBefore(contentArea, resultsContainer.firstChild);
        }
        
        clearElement(contentArea);
        
        const loading = document.createElement('div');
        loading.className = 'loading-message';
        loading.style.textAlign = 'center';
        loading.style.padding = '2rem';
        loading.style.color = '#666';
        loading.textContent = t.loading;
        contentArea.appendChild(loading);
    }

    function showError() {
        const lang = getLanguage();
        const t = translations[lang];
        
        let contentArea = resultsContainer.querySelector('.results-content-area');
        if (!contentArea) {
            contentArea = document.createElement('div');
            contentArea.className = 'results-content-area';
            resultsContainer.insertBefore(contentArea, resultsContainer.firstChild);
        }
        
        clearElement(contentArea);
        
        const error = document.createElement('div');
        error.className = 'error-message';
        error.style.textAlign = 'center';
        error.style.padding = '2rem';
        error.style.color = '#dc3545';
        error.textContent = t.error;
        contentArea.appendChild(error);
    }

    function showNoResults() {
        const lang = getLanguage();
        const t = translations[lang];
        
        let contentArea = resultsContainer.querySelector('.results-content-area');
        if (!contentArea) {
            contentArea = document.createElement('div');
            contentArea.className = 'results-content-area';
            resultsContainer.insertBefore(contentArea, resultsContainer.firstChild);
        }
        
        clearElement(contentArea);
        
        const noResults = document.createElement('div');
        noResults.className = 'no-results-message';
        noResults.style.textAlign = 'center';
        noResults.style.padding = '2rem';
        noResults.style.color = '#666';
        noResults.textContent = t.noResults;
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
            // Pagination stays - user can go back!
            updatePagination(currentPage);
        }
    }

    function displayResults(companies, page) {
        const lang = getLanguage();

        let contentArea = resultsContainer.querySelector('.results-content-area');
        if (!contentArea) {
            contentArea = document.createElement('div');
            contentArea.className = 'results-content-area';
            resultsContainer.insertBefore(contentArea, resultsContainer.firstChild);
        }
        
        clearElement(contentArea);

        const hasResults = companies && companies.length > 0;

        if (!hasResults) {
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

        // ALWAYS update pagination - never remove it
        updatePagination(page);
    }

    function updatePagination(page) {
        const lang = getLanguage();
        const t = translations[lang];

        // Find or create pagination container
        let paginationContainer = resultsContainer.querySelector('.pagination-container');
        
        if (!paginationContainer) {
            paginationContainer = document.createElement('div');
            paginationContainer.className = 'pagination-container';
            resultsContainer.appendChild(paginationContainer);
        }

        // Clear and rebuild pagination
        clearElement(paginationContainer);

        // Previous button
        const prevLink = document.createElement('a');
        prevLink.href = '#';
        prevLink.className = 'page-link';
        prevLink.textContent = t.previous;
        
        if (page <= 1) {
            prevLink.classList.add('disabled');
            prevLink.style.opacity = '0.4';
            prevLink.style.cursor = 'not-allowed';
            prevLink.style.pointerEvents = 'none';
        } else {
            prevLink.addEventListener('click', (e) => {
                e.preventDefault();
                performSearch(page - 1);
            });
        }
        paginationContainer.appendChild(prevLink);

        // Current page indicator
        const pageInfo = document.createElement('span');
        pageInfo.className = 'page-link active';
        pageInfo.textContent = `${t.page} ${page}`;
        paginationContainer.appendChild(pageInfo);

        // Next button
        const nextLink = document.createElement('a');
        nextLink.href = '#';
        nextLink.className = 'page-link';
        nextLink.textContent = t.next;
        
        if (lastResultCount < resultsPerPage) {
            nextLink.classList.add('disabled');
            nextLink.style.opacity = '0.4';
            nextLink.style.cursor = 'not-allowed';
            nextLink.style.pointerEvents = 'none';
        } else {
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

    // Listen for search trigger
    document.addEventListener('searchTriggered', () => {
        performSearch(1);
    });

    // Re-render on language change
    document.addEventListener('stateChange', () => {
        performSearch(currentPage);
    });

    // Initial load
    performSearch(1);
});