<template>
  <div class="home">
    <h1>Crypto Dashboard</h1>
    <LoadingSpinner v-if="store.loading" />
    <div v-if="store.error">{{ store.error }}</div>
    <CryptoTable v-if="!store.loading && store.coins.length" :coins="store.coins" />
  </div>
</template>

<script>
import { useCryptoStore } from '../store';
import CryptoTable from '../components/CryptoTable.vue';
import LoadingSpinner from '../components/LoadingSpinner.vue';

export default {
  components: { CryptoTable, LoadingSpinner },
  setup() {
    const store = useCryptoStore();
    store.getCoinList();
    return { store };
  },
};
</script>