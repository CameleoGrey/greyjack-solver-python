use rand::{rngs::StdRng, SeedableRng, Rng};
use rand_distr::{Distribution, Uniform, Normal};
use std::cell::RefCell;
use once_cell::sync::Lazy;

// Thread-local RNG - much faster than creating new instances
thread_local! {
    static THREAD_RNG: RefCell<StdRng> = RefCell::new(StdRng::from_entropy());
}

/// Central RNG utilities - replaces the problematic functions in math_utils.rs
pub struct RngUtils;

impl RngUtils {
    /// Get a random integer in range [start, end)
    pub fn get_random_id(start_id: usize, end_exclusive: usize) -> usize {
        THREAD_RNG.with(|rng| {
            let mut rng = rng.borrow_mut();
            rng.gen_range(start_id..end_exclusive)
        })
    }

    /// Get a random f64 in range [0, 1)
    pub fn get_random_f64() -> f64 {
        THREAD_RNG.with(|rng| rng.borrow_mut().gen())
    }

    /// Get a random f64 in specified range
    pub fn get_random_f64_range(min: f64, max: f64) -> f64 {
        THREAD_RNG.with(|rng| {
            let mut rng = rng.borrow_mut();
            Uniform::new(min, max).sample(&mut *rng)
        })
    }

    /// Get a random sample from normal distribution
    pub fn get_normal_sample(mean: f64, std_dev: f64) -> f64 {
        THREAD_RNG.with(|rng| {
            let mut rng = rng.borrow_mut();
            Normal::new(mean, std_dev).unwrap().sample(&mut *rng)
        })
    }

    /// Choose random elements without replacement
    pub fn choice_without_replacement<T: Clone>(objects: &[T], n: usize) -> Vec<T> {
        if n > objects.len() {
            panic!("Cannot choose {} elements from {} without replacement", n, objects.len());
        }

        THREAD_RNG.with(|rng| {
            let mut rng = rng.borrow_mut();
            let mut indices: Vec<usize> = (0..objects.len()).collect();
            
            // Fisher-Yates shuffle (partial)
            for i in 0..n {
                let j = rng.gen_range(i..indices.len());
                indices.swap(i, j);
            }
            
            indices[..n].iter().map(|&i| objects[i].clone()).collect()
        })
    }

    /// Choose random elements with replacement
    pub fn choice_with_replacement<T: Clone>(objects: &[T], n: usize) -> Vec<T> {
        THREAD_RNG.with(|rng| {
            let mut rng = rng.borrow_mut();
            (0..n).map(|_| {
                let idx = rng.gen_range(0..objects.len());
                objects[idx].clone()
            }).collect()
        })
    }

    /// Shuffle a slice in place
    pub fn shuffle<T>(slice: &mut [T]) {
        THREAD_RNG.with(|rng| {
            let mut rng = rng.borrow_mut();
            
            // Fisher-Yates shuffle
            for i in (1..slice.len()).rev() {
                let j = rng.gen_range(0..=i);
                slice.swap(i, j);
            }
        })
    }

    /// Get random boolean with given probability
    pub fn random_bool(probability: f64) -> bool {
        THREAD_RNG.with(|rng| {
            let mut rng = rng.borrow_mut();
            rng.gen::<f64>() < probability
        })
    }
}