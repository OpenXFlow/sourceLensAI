import axios from 'axios';

const API_BASE_URL = 'https://api.coingecko.com/api/v3';

export async function fetchCoins() {
    const response = await axios.get(`${API_BASE_URL}/coins/markets`, {
        params: {
            vs_currency: 'usd',
            order: 'market_cap_desc',
            per_page: 50,
            page: 1,
        },
    });
    return response.data;
}

export async function fetchCoinData(coinId) {
    const response = await axios.get(`${API_BASE_URL}/coins/${coinId}/market_chart`, {
        params: {
            vs_currency: 'usd',
            days: '30',
        },
    });
    return response.data;
}