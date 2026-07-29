// dashboard.js - JavaScript para FunStuffBarn Dashboard

document.addEventListener('DOMContentLoaded', function() {
    // Elementos
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const mainContent = document.querySelector('.main-content');
    const currentTimeEl = document.getElementById('currentTime');
    const lastUpdateEl = document.getElementById('lastUpdate');
    
    // Toggle sidebar en móvil
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
        });
    }
    
    // Cerrar sidebar al hacer click fuera en móvil
    document.addEventListener('click', function(e) {
        if (window.innerWidth < 992 && 
            sidebar.classList.contains('show') && 
            !sidebar.contains(e.target) && 
            !sidebarToggle.contains(e.target)) {
            sidebar.classList.remove('show');
        }
    });
    
    // Actualizar hora
    function updateTime() {
        const now = new Date();
        if (currentTimeEl) {
            currentTimeEl.textContent = now.toLocaleTimeString('es-ES');
        }
    }
    updateTime();
    setInterval(updateTime, 1000);
    
    // Auto-refresh para página de monitoring
    if (window.location.pathname === '/monitoring') {
        setInterval(() => {
            // Recargar solo los logs via AJAX
            fetch('/api/logs/coordinador.log?lines=50')
                .then(r => r.json())
                .then(data => {
                    const logEl = document.getElementById('log-coordinador');
                    if (logEl) logEl.textContent = data.content;
                });
        }, 30000);
    }
    
    // Función genérica para filtrar tablas
    window.filterTable = function(searchInputId, tableId, filterSelectors) {
        const search = document.getElementById(searchInputId)?.value.toLowerCase() || '';
        const rows = document.querySelectorAll(`#${tableId} tbody tr`);
        
        rows.forEach(row => {
            let show = true;
            
            if (search) {
                const text = row.textContent.toLowerCase();
                show = text.includes(search);
            }
            
            if (filterSelectors) {
                filterSelectors.forEach(({selectId, dataAttr}) => {
                    const filterValue = document.getElementById(selectId)?.value;
                    if (filterValue && row.dataset[dataAttr] !== filterValue) {
                        show = false;
                    }
                });
            }
            
            row.style.display = show ? '' : 'none';
        });
    };
    
    // Toast notifications
    window.showToast = function(message, type = 'info') {
        const toastContainer = document.getElementById('toastContainer') || createToastContainer();
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        toastContainer.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
        bsToast.show();
        toast.addEventListener('hidden.bs.toast', () => toast.remove());
    };
    
    function createToastContainer() {
        const container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
        return container;
    }
    
    // Confirmación genérica
    window.confirmAction = function(message, callback) {
        if (confirm(message)) {
            callback();
        }
    };
    
    // API helper
    window.api = {
        get: async (url) => {
            const res = await fetch(url);
            if (!res.ok) throw new Error(await res.text());
            return res.json();
        },
        post: async (url, data) => {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            if (!res.ok) throw new Error(await res.text());
            return res.json();
        }
    };
});

// Funciones para reportes
function downloadReport(filename) {
    window.location.href = `/reports/${encodeURIComponent(filename)}/download`;
}

function filterReports() {
    const filter = document.getElementById('prefixFilter').value;
    const rows = document.querySelectorAll('#reportsTable tbody tr');
    rows.forEach(row => {
        row.style.display = !filter || row.dataset.prefix === filter ? '' : 'none';
    });
}

// Funciones para prompts
function filterPrompts() {
    const search = document.getElementById('promptSearch')?.value.toLowerCase() || '';
    const category = document.getElementById('categoryFilter')?.value || '';
    const rows = document.querySelectorAll('#promptsTable tbody tr');
    
    rows.forEach(row => {
        const name = row.dataset.name || '';
        const cat = row.dataset.category || '';
        const matchSearch = !search || name.includes(search);
        const matchCat = !category || cat === category;
        row.style.display = matchSearch && matchCat ? '' : 'none';
    });
}

// Funciones para diseños
function filterDisenos() {
    const search = document.getElementById('disenosSearch')?.value.toLowerCase() || '';
    const category = document.getElementById('categoryFilterDisenos')?.value || '';
    const ext = document.getElementById('extFilter')?.value || '';
    const cards = document.querySelectorAll('.diseno-card');
    
    cards.forEach(card => {
        const name = card.dataset.name || '';
        const cat = card.dataset.category || '';
        const cardExt = card.dataset.ext || '';
        
        const matchSearch = !search || name.includes(search);
        const matchCat = !category || cat === category;
        const matchExt = !ext || cardExt === ext;
        
        card.style.display = matchSearch && matchCat && matchExt ? '' : 'none';
    });
}

// Funciones para secrets
async function updateSecret(key) {
    const value = document.getElementById(`secret-${key}`)?.value;
    if (!value) return;
    
    try {
        const res = await fetch('/secrets/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ key, value })
        });
        const data = await res.json();
        if (data.success) {
            showToast('Variable actualizada', 'success');
        } else {
            showToast('Error: ' + data.message, 'danger');
        }
    } catch (e) {
        showToast('Error de conexión', 'danger');
    }
}

function toggleSecretVisibility(key) {
    const input = document.getElementById(`secret-${key}`);
    const btn = document.getElementById(`toggle-${key}`);
    if (input.type === 'password') {
        input.type = 'text';
        btn.innerHTML = '<i class="bi bi-eye-slash"></i>';
    } else {
        input.type = 'password';
        btn.innerHTML = '<i class="bi bi-eye"></i>';
    }
}