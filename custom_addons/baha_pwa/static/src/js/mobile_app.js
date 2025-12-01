/** @odoo-module **/

import { Component, useState, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Main Mobile App Component
 */
export class OdooMobileApp extends Component {
    setup() {
        this.orm = useService("orm");
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        
        this.state = useState({
            menuOpen: false,
            currentView: 'dashboard',
            currentModel: null,
            records: [],
            loading: false,
            searchQuery: '',
            user: {},
            dashboardData: {},
            installPromptVisible: false,
        });
        
        this.deferredPrompt = null;
        
        onMounted(() => {
            this.initializeApp();
            this.registerServiceWorker();
            this.setupInstallPrompt();
        });
    }
    
    /**
     * Initialize the mobile app
     */
    async initializeApp() {
        try {
            // Get current user info
            this.state.user = await this.rpc('/web/session/get_session_info');
            
            // Load dashboard by default
            await this.loadDashboard();
        } catch (error) {
            console.error('Failed to initialize app:', error);
            this.notification.add('Failed to load app', { type: 'danger' });
        }
    }
    
    /**
     * Register service worker for PWA
     */
    registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/service-worker.js')
                .then((registration) => {
                    console.log('Service Worker registered:', registration);
                    
                    // Check for updates
                    registration.addEventListener('updatefound', () => {
                        const newWorker = registration.installing;
                        newWorker.addEventListener('statechange', () => {
                            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                this.notification.add('New version available. Please refresh.', {
                                    type: 'info',
                                    sticky: true,
                                });
                            }
                        });
                    });
                })
                .catch((error) => {
                    console.error('Service Worker registration failed:', error);
                });
        }
    }
    
    /**
     * Setup PWA install prompt
     */
    setupInstallPrompt() {
        window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            this.deferredPrompt = e;
            this.state.installPromptVisible = true;
        });
        
        window.addEventListener('appinstalled', () => {
            console.log('PWA installed successfully');
            this.state.installPromptVisible = false;
            this.notification.add('App installed successfully!', { type: 'success' });
        });
    }
    
    /**
     * Install PWA
     */
    async installApp() {
        if (!this.deferredPrompt) {
            return;
        }
        
        this.deferredPrompt.prompt();
        const { outcome } = await this.deferredPrompt.userChoice;
        
        console.log(`User response to install prompt: ${outcome}`);
        this.deferredPrompt = null;
        this.state.installPromptVisible = false;
    }
    
    /**
     * Toggle navigation menu
     */
    toggleMenu() {
        this.state.menuOpen = !this.state.menuOpen;
    }
    
    /**
     * Load dashboard view
     */
    async loadDashboard() {
        this.state.currentView = 'dashboard';
        this.state.menuOpen = false;
        this.state.loading = true;
        
        try {
            // Load counts for different modules
            const [salesCount, purchasesCount, contactsCount, deliveriesCount] = await Promise.all([
                this.getRecordCount('sale.order'),
                this.getRecordCount('purchase.order'),
                this.getRecordCount('res.partner'),
                this.getRecordCount('stock.picking'),
            ]);
            
            this.state.dashboardData = {
                sales: salesCount,
                purchases: purchasesCount,
                contacts: contactsCount,
                deliveries: deliveriesCount,
            };
            
        } catch (error) {
            console.error('Failed to load dashboard:', error);
            this.notification.add('Failed to load dashboard', { type: 'danger' });
        } finally {
            this.state.loading = false;
        }
    }
    
    /**
     * Get record count for a model
     */
    async getRecordCount(model) {
        try {
            return await this.orm.searchCount(model, []);
        } catch (error) {
            console.error(`Failed to count records for ${model}:`, error);
            return 0;
        }
    }
    
    /**
     * Load records for a specific model
     */
    async loadModule(model, title) {
        this.state.currentView = 'list';
        this.state.currentModel = model;
        this.state.menuOpen = false;
        this.state.loading = true;
        this.state.searchQuery = '';
        
        try {
            const records = await this.orm.searchRead(
                model,
                [],
                ['id', 'display_name', 'create_date'],
                { limit: 100 }
            );
            
            this.state.records = records;
        } catch (error) {
            console.error(`Failed to load records for ${model}:`, error);
            this.notification.add(`Failed to load ${title}`, { type: 'danger' });
            this.state.records = [];
        } finally {
            this.state.loading = false;
        }
    }
    
    /**
     * Search records
     */
    async searchRecords() {
        if (!this.state.currentModel || !this.state.searchQuery) {
            return;
        }
        
        this.state.loading = true;
        
        try {
            const domain = [['display_name', 'ilike', this.state.searchQuery]];
            const records = await this.orm.searchRead(
                this.state.currentModel,
                domain,
                ['id', 'display_name', 'create_date'],
                { limit: 100 }
            );
            
            this.state.records = records;
        } catch (error) {
            console.error('Search failed:', error);
            this.notification.add('Search failed', { type: 'danger' });
        } finally {
            this.state.loading = false;
        }
    }
    
    /**
     * View record details
     */
    async viewRecord(recordId) {
        if (!this.state.currentModel) {
            return;
        }
        
        try {
            const record = await this.orm.read(this.state.currentModel, [recordId]);
            console.log('Record details:', record);
            
            // Here you would open a detail view/modal
            this.notification.add(`Viewing record: ${record[0].display_name}`, { type: 'info' });
        } catch (error) {
            console.error('Failed to load record:', error);
            this.notification.add('Failed to load record details', { type: 'danger' });
        }
    }
    
    /**
     * Create new record
     */
    createNewRecord() {
        if (!this.state.currentModel) {
            this.notification.add('Please select a module first', { type: 'warning' });
            return;
        }
        
        // Here you would open a create form/modal
        this.notification.add('Create new record - Feature coming soon', { type: 'info' });
    }
    
    /**
     * Format date for display
     */
    formatDate(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        return date.toLocaleDateString();
    }
    
    /**
     * Get filtered records based on search
     */
    get filteredRecords() {
        if (!this.state.searchQuery) {
            return this.state.records;
        }
        
        const query = this.state.searchQuery.toLowerCase();
        return this.state.records.filter(record => 
            record.display_name.toLowerCase().includes(query)
        );
    }
}

OdooMobileApp.template = "baha_pwa.MobileApp";

// Register the component
registry.category("actions").add("baha_pwa.mobile_app", OdooMobileApp);

/**
 * Offline Storage Manager
 */
export class OfflineStorageManager {
    constructor() {
        this.dbName = 'odoo_mobile_offline';
        this.dbVersion = 1;
        this.db = null;
    }
    
    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.dbVersion);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                resolve();
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                // Create object stores
                if (!db.objectStoreNames.contains('records')) {
                    db.createObjectStore('records', { keyPath: 'id' });
                }
                
                if (!db.objectStoreNames.contains('pending_changes')) {
                    db.createObjectStore('pending_changes', { autoIncrement: true });
                }
            };
        });
    }
    
    async saveRecord(model, record) {
        const transaction = this.db.transaction(['records'], 'readwrite');
        const store = transaction.objectStore('records');
        
        return new Promise((resolve, reject) => {
            const request = store.put({ ...record, _model: model });
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
    
    async getRecords(model) {
        const transaction = this.db.transaction(['records'], 'readonly');
        const store = transaction.objectStore('records');
        
        return new Promise((resolve, reject) => {
            const request = store.getAll();
            request.onsuccess = () => {
                const records = request.result.filter(r => r._model === model);
                resolve(records);
            };
            request.onerror = () => reject(request.error);
        });
    }
}

// Initialize offline storage
const offlineStorage = new OfflineStorageManager();
offlineStorage.init().catch(console.error);