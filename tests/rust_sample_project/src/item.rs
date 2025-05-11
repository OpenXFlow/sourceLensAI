// V main.rs
mod item; // Deklaruje modul item.rs
use crate::item::Item; // Sprístupní Item štruktúru

fn main() {
    let mut my_item = Item::new(1, String::from("Test Item"), 123.45);
    println!("{}", my_item); // Vďaka Display trait
    my_item.mark_as_processed();
    println!("{:?}", my_item); // Vďaka Debug trait
}