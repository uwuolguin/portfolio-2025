import { getLanguage, apiRequest } from '../../../0-shared-components/utils/shared-functions.js';
import { sanitizeText, sanitizeURL, sanitizeEmail, sanitizePhone } from '../../../0-shared-components/utils/sanitizer.js';

document.addEventListener('DOMContentLoaded', () => {
    const resultsContainer = document.getElementById('results-container');
    const cardsPerPage = 5;
    const numbersPerPagination = 3;
    let currentPage = 1;

    /**
     * SECURE RENDERING: Use DOM methods instead of innerHTML
     */
    const renderCards = (companies) => {
        const fragment = document.createDocumentFragment();
        
        companies.forEach(company => {
            // Sanitize ALL user inputs BEFORE rendering
            const safeName = sanitizeText(company.name);
            const safeDescription = sanitizeText(company.description);
            const safeAddress = sanitizeText(company.address);
            const safePhone = sanitizePhone(company.phone);
            const safeEmail = sanitizeEmail(company.email);
            const safeImageURL = sanitizeURL(company.image);
            
            // Create card using DOM methods (NO innerHTML)
            const card = document.createElement('div');
            card.className = 'business-card';
            
            // Image section
            const pictureDiv = document.createElement('div');
            pictureDiv.className = 'card-picture';
            
            const img = document.createElement('img');
            img.src = safeImageURL || 'https://via.placeholder.com/400x220?text=No+Image';
            img.alt = 'Product Image';
            img.onerror = function() {
                this.src = 'https://via.placeholder.com/400x220?text=No+Image';
            };
            pictureDiv.appendChild(img);
            
            // Details section
            const detailsDiv = document.createElement('div');
            detailsDiv.className = 'card-details';
            
            // Name (textContent is XSS-proof)
            const nameH3 = document.createElement('h3');
            nameH3.className = 'business-name';
            nameH3.textContent = safeName;  // SAFE: textContent doesn't parse HTML
            
            // Description
            const descP = document.createElement('p');
            descP.className = 'concise-description';
            descP.textContent = safeDescription;
            
            // Address
            const addrP = document.createElement('p');
            addrP.className = 'location';
            addrP.textContent = safeAddress;
            
            // Phone
            const phoneP = document.createElement('p');
            phoneP.className = 'phone';
            phoneP.textContent = safePhone;
            
            // Email
            const emailP = document.createElement('p');
            emailP.className = 'mail';
            emailP.textContent = safeEmail;
            
            // Assemble card
            detailsDiv.appendChild(nameH3);
            detailsDiv.appendChild(descP);
            detailsDiv.appendChild(addrP);
            detailsDiv.appendChild(phoneP);
            detailsDiv.appendChild(emailP);
            
            card.appendChild(pictureDiv);
            card.appendChild(detailsDiv);
            
            fragment.appendChild(card);
        });
        
        return fragment;
    };

    const renderPagination = () => {
        let half = Math.floor(numbersPerPagination / 2);
        let startPage = Math.max(1, currentPage - half);
        let endPage = startPage + numbersPerPagination - 1;

        // Create pagination using DOM methods
        const paginationDiv = document.createElement('div');
        paginationDiv.className = 'pagination-container';
        
        // Previous button
        const prevLink = document.createElement('a');
        prevLink.href = '#';
        prevLink.className = 'page-link prev-link';
        prevLink.textContent = '«';
        paginationDiv.appendChild(prevLink);
        
        // Page numbers
        for (let i = startPage; i <= endPage; i++) {
            const pageLink = document.createElement('a');
            pageLink.href = '#';
            pageLink.className = 'page-link' + (i === currentPage ? ' active' : '');
            pageLink.dataset.page = i;
            pageLink.textContent = i;
            paginationDiv.appendChild(pageLink);
        }
        
        // Next button
        const nextLink = document.createElement('a');
        nextLink.href = '#';
        nextLink.className = 'page-link next-link';
        nextLink.textContent = '»';
        paginationDiv.appendChild(nextLink);
        
        return paginationDiv;
    };

    const fetchAndRender = async () => {
        try {
            const currentLanguage = getLanguage();
            
            const searchQuery = document.getElementById('search-query')?.value || '';
            const communeFilter = document.querySelector('[data-dropdown-id="commune"] .dropdown-selected')?.getAttribute('data-value') || '';
            const productFilter = document.querySelector('[data-dropdown-id="product"] .dropdown-selected')?.getAttribute('data-value') || '';
            
            const params = new URLSearchParams({
                lang: currentLanguage,
                limit: cardsPerPage.toString(),
                offset: ((currentPage - 1) * cardsPerPage).toString()
            });
            
            const allCommunesText = currentLanguage === 'es' ? 'Todas Las Comunas' : 'All Communes';
            const allProductsText = currentLanguage === 'es' ? 'Todos Los Productos' : 'All Products';
            
            if (searchQuery) params.append('q', searchQuery);
            if (communeFilter && communeFilter !== allCommunesText) params.append('commune', communeFilter);
            if (productFilter && productFilter !== allProductsText) params.append('product', productFilter);
            
            const response = await apiRequest(`/api/v1/companies/search?${params.toString()}`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch companies');
            }
            
            const companies = await response.json();
            
            const transformedCompanies = companies.map(company => ({
                id: company.uuid,
                name: company.name,
                description: company.description,
                address: company.address,
                phone: company.phone,
                email: company.email,
                image: company.img_url || 'https://via.placeholder.com/400x220?text=No+Image'
            }));

            // Clear and render (using DOM methods, NOT innerHTML)
            resultsContainer.textContent = '';  // Clear safely
            
            const resultsGrid = document.createElement('div');
            resultsGrid.className = 'results-grid';
            
            if (transformedCompanies.length > 0) {
                const cardsFragment = renderCards(transformedCompanies);
                resultsGrid.appendChild(cardsFragment);
            } else {
                const noResults = document.createElement('div');
                noResults.style.cssText = 'text-align: center; padding: 40px; color: #666;';
                noResults.textContent = currentLanguage === 'es' ? 'No se encontraron empresas' : 'No companies found';
                resultsGrid.appendChild(noResults);
            }
            
            const pagination = renderPagination();
            
            resultsContainer.appendChild(resultsGrid);
            resultsContainer.appendChild(pagination);

        } catch (error) {
            console.error("Error fetching companies:", error);
            
            resultsContainer.textContent = '';
            const errorDiv = document.createElement('div');
            errorDiv.style.cssText = 'text-align: center; padding: 40px; color: #d32f2f;';
            errorDiv.textContent = getLanguage() === 'es' ? 'Error al cargar las empresas' : 'Error loading companies';
            resultsContainer.appendChild(errorDiv);
        }
    };

    // Event delegation for pagination
    resultsContainer.addEventListener('click', (e) => {
        const link = e.target.closest('.page-link');
        if (!link) return;
        e.preventDefault();

        if (link.classList.contains('prev-link')) {
            currentPage = Math.max(1, currentPage - 1);
        } else if (link.classList.contains('next-link')) {
            currentPage = currentPage + 1;
        } else {
            currentPage = parseInt(link.dataset.page);
        }

        fetchAndRender();
    });

    document.addEventListener("languageChange", () => {
        fetchAndRender();
    });

    document.addEventListener("searchTriggered", () => {
        currentPage = 1;
        fetchAndRender();
    });

    fetchAndRender();
});