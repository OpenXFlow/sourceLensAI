<template>
  <div class="coin-detail">
    <button @click="$router.back()">Back</button>
    <h2>Details for {{ id }}</h2>
    <LoadingSpinner v-if="store.loading" />
    <div v-if="store.error">{{ store.error }}</div>
    <CryptoChart v-if="store.selectedCoin" :chart-data="store.selectedCoin.prices" />
  </div>
</template>

<script>
import { useCryptoStore } from '../store';
import CryptoChart from '../components/CryptoChart.vue';
import LoadingSpinner from '../components/LoadingSpinner.vue';

export default {
  props: ['id'],
  components: { CryptoChart, LoadingSpinner },
  setup(props) {
    const store = useCryptoStore();
    store.getCoinDetails(props.id);
    return { store };
  },
};
</script>