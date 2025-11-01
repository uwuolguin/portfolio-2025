    // TODO: Replace localStorage-based login state with a server-side session check.
    //       Future plan: use secure HttpOnly cookies + /api/check-session endpoint
    //       instead of reading isLoggedIn from localStorage.
    export function getLoginState() {
        let value = localStorage.getItem("isLoggedIn");
        if (value === null) {
            localStorage.setItem("isLoggedIn", "false");
            return false;
        }
        return value === "true";
    }

    export function setLoginState(hasLogged) {
        localStorage.setItem("isLoggedIn", hasLogged.toString());
        
        // Clear company publish state when logging out
        if (!hasLogged) {
            localStorage.setItem("hasPublishedCompany", "false");
        }
        
        document.dispatchEvent(new CustomEvent("userHasLogged"));
    }

    // TODO: In the future, consider storing the language preference in the server-side
    //       session or user profile instead of localStorage for better security.
    export function getLanguage() {
        let lang = localStorage.getItem("lang");
        if (!lang) {
            localStorage.setItem("lang", "es"); // default Spanish
            return "es";
        }
        return lang;
    }

    export function setLanguage(Lang) {
        localStorage.setItem("lang", Lang);
        document.dispatchEvent(new CustomEvent("languageChange"));
    }

    // Company publish state - only true when logged in
    export function getCompanyPublishState() {
        // If not logged in, always return false
        if (!getLoginState()) {
            return false;
        }
        
        let value = localStorage.getItem("hasPublishedCompany");
        if (value === null) {
            localStorage.setItem("hasPublishedCompany", "false");
            return false;
        }
        return value === "true";
    }

    export function setCompanyPublishState(hasPublished) {
        // Only allow true if logged in
        if (hasPublished && !getLoginState()) {
            return; // Do nothing if trying to set true while not logged in
        }
        
        localStorage.setItem("hasPublishedCompany", hasPublished.toString());
        document.dispatchEvent(new CustomEvent("companyPublishStateChange"));
    }

    export function initStorageListener() {
        window.addEventListener("storage", (event) => {
            if (event.key === "lang" || event.key === "isLoggedIn" || event.key === "hasPublishedCompany") {
                location.reload();
            }
        });
    }

    // Get stored company data
    export function getCompanyData() {
        return JSON.parse(localStorage.getItem('companyData')) || null;
    }

    // Set/update company data
    export function setCompanyData(data) {
        if (data === null) {
            localStorage.removeItem('companyData');
            setCompanyPublishState(false);
        } else {
            localStorage.setItem('companyData', JSON.stringify(data));
            setCompanyPublishState(true);
        }
        
        // Dispatch custom event for data change
        document.dispatchEvent(new CustomEvent('companyDataChange'));
    }