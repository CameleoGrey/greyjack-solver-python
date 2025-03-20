

#[macro_export]
macro_rules! build_concrete_sum_scores_function {

    ($sum_function_name: ident, $score_type: ident) => {
        #[pyfunction]
        #[pyo3(signature = (scores_vec, constraint_weights, constraints_names_list))]
        pub fn $sum_function_name(
            scores_vec: Vec<Vec<$score_type>>, 
            constraint_weights: HashMap<String, f64>, 
            constraints_names_list: Vec<String>) -> Vec<$score_type> {

                let constraints_count = scores_vec.len();
                let samples_count = scores_vec[0].len();
                let mut scores: Vec<$score_type> = vec![$score_type::get_null_score(); samples_count];

                for i in 0..samples_count {
                    for j in 0..constraints_count {
                        let constraint_weight = constraint_weights.get(&constraints_names_list[j]).unwrap();
                        let weighted_score = scores_vec[j][i].mul(*constraint_weight);
                        scores[i] += weighted_score;
                    }
                }

                return scores;
            }

    }
}