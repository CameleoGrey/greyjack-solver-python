


use std::fmt::Debug;
use std::ops::AddAssign;
use std::cmp::Ordering;

#[derive(Debug, Clone)]
pub struct Individual<ScoreType>
where ScoreType: Clone + AddAssign + PartialEq + PartialOrd + Ord + Debug {
    pub variable_values: Vec<f64>,
    pub score: ScoreType
}

impl<ScoreType> Individual<ScoreType>
where ScoreType: Clone + AddAssign + PartialEq + PartialOrd + Ord + Debug {
    pub fn new(variable_values: Vec<f64>, score: ScoreType) -> Self {
        Self {
            variable_values: variable_values,
            score: score
        }
    }
}

impl<ScoreType> Ord for Individual<ScoreType>
where ScoreType: Clone + AddAssign + PartialEq + PartialOrd + Ord + Debug {

    fn cmp(&self, other: &Self) -> Ordering {
        self.score.cmp(&other.score)
    }
    
}

impl<ScoreType> Eq for Individual<ScoreType>
where ScoreType: Clone + AddAssign + PartialEq + PartialOrd + Ord + Debug {
    
}

impl<ScoreType> PartialEq for Individual<ScoreType>
where ScoreType: Clone + AddAssign + PartialEq + PartialOrd + Ord + Debug  {
    fn eq(&self, other: &Self) -> bool {
        self.score.eq(&other.score)
    }

    fn ne(&self, other: &Self) -> bool {
        self.score.ne(&other.score)
    }
}

impl<ScoreType> PartialOrd for Individual<ScoreType>
where ScoreType: Clone + AddAssign + PartialEq + PartialOrd + Ord + Debug {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        self.score.partial_cmp(&other.score)
    }
}
