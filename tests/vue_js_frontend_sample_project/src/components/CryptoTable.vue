<template>
  <table>
    <thead>
      <tr>
        <th>Rank</th>
        <th>Name</th>
        <th>Price (USD)</th>
        <th>Market Cap</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="coin in coins" :key="coin.id" @click="goToDetail(coin.id)">
        <td>{{ coin.market_cap_rank }}</td>
        <td>{{ coin.name }}</td>
        <td>{{ coin.current_price }}</td>
        <td>{{ coin.market_cap }}</td>
      </tr>
    </tbody>
  </table>
</template>

<script>
export default {
  props: ['coins'],
  methods: {
    goToDetail(id) {
      this.$router.push(`/coin/${id}`);
    }
  }
};
</script>
<style scoped>
  tr:hover { cursor: pointer; background-color: #f0f0f0; }
</style>