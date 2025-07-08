import { defineStore } from 'pinia';
import { fetchCoins, fetchCoinData } from './services/cryptoApi';

export const useCryptoStore = defineStore('crypto', {
  state: () => ({
    coins: [],
    loading: false,
    error: null,
    selectedCoin: null,
  }),
  actions: {
    async getCoinList() {
      this.loading = true;
      this.error = null;
      try {
        this.coins = await fetchCoins();
      } catch (error) {
        this.error = 'Failed to fetch coin list.';
      } finally {
        this.loading = false;
      }
    },
    async getCoinDetails(id) {
        this.loading = true;
        this.error = null;
        try {
          this.selectedCoin = await fetchCoinData(id);
        } catch (error) {
          this.error = `Failed to fetch details for ${id}.`;
        } finally {
          this.loading = false;
        }
    },
  },
});