
use rand::{rngs::StdRng, seq::SliceRandom, SeedableRng};
use rand_distr::{Distribution, Uniform};
use std::{collections::HashSet, hash::Hash};

pub fn rint(x: f64) -> f64 {
    if (x - x.floor()).abs() < (x.ceil() - x).abs() {x.floor()} else {x.ceil()}
}

pub fn round(value: f64, precision: u64) -> f64 {
    let multiplier = (10.0 as f64).powf(precision as f64);
    value.floor() + ((value - value.floor()) * multiplier).floor() / multiplier
}

pub fn get_random_id(start_id: usize, end_exclusive: usize) -> usize {
    Uniform::new(start_id, end_exclusive).sample(&mut StdRng::from_entropy())
}

pub fn choice<T>(objects: &Vec<T>, n: usize, replace: bool) -> Vec<T>
where T: Clone {
    if replace == true {
        choice_with_replacement(objects, n)
    } else {
        choice_without_replacement(objects, n)
    }
}

fn choice_with_replacement<T>(objects: &Vec<T>, n: usize) -> Vec<T>
where T: Clone {
    
    let objects_count = objects.len();
    let chosen_objects: Vec<T> = (0..n).into_iter().map(|i| objects[get_random_id(0, objects_count)].clone()).collect();
    return chosen_objects;
}

fn choice_without_replacement<T>(objects: &Vec<T>, n: usize) -> Vec<T>
where T: Clone {

    if n > objects.len() {
        panic!("There are less objects tnan can be chosen from collection without replacement");
    }
    
    let mut random_ids:Vec<usize> = (0..objects.len()).collect();
    random_ids.shuffle(&mut StdRng::from_entropy());
    let chosen_objects: Vec<T> = (0..n).into_iter().map(|i| objects[random_ids[i]].clone()).collect();

    return chosen_objects;
}

/*pub fn select_non_tabu_ids<T>(objects: &Vec<T>, n: usize, group: bool) -> Vec<T>
where T: Clone {



    /*
    def _select_non_tabu_ids(self, selection_size, group_name, right_end):
        random_ids = []
        while len(random_ids) != selection_size:
            random_id = self.generator.integers(0, right_end, 1)[0]

            if random_id not in self.tabu_ids_sets_dict[group_name]:
                self.tabu_ids_sets_dict[group_name].add( random_id )
                self.tabu_ids_list_dict[group_name].append( random_id )
                random_ids.append( random_id )

                if len(self.tabu_ids_list_dict[group_name]) > self.tabu_entity_size_dict[group_name]:
                    self.tabu_ids_sets_dict[group_name].remove( self.tabu_ids_list_dict[group_name].pop(0) )

        return random_ids
    */
}*/
