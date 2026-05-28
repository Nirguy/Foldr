import unittest
import numpy as np
import pandas as pd
from data_authenticator import DatasetAuthenticator

class TestDatasetAuthenticator(unittest.TestCase):
    def setUp(self):
        # Set up a random state for deterministic tests
        np.random.seed(42)
        
    def test_benford_applicability(self):
        """
        Tests if Benford's Law check correctly identifies narrow-span datasets as inapplicable.
        """
        # Narrow range data (values between 10 and 12, less than 1.5 orders of magnitude)
        narrow_data = pd.Series(np.random.uniform(10, 12, size=100))
        auth = DatasetAuthenticator(pd.DataFrame({"col": narrow_data}))
        res = auth.test_benford(narrow_data)
        
        self.assertFalse(res["is_applicable"])
        self.assertEqual(res["status"], "Inapplicable")
        
        # Wide range data (spanning 4 orders of magnitude)
        wide_data = pd.Series(10 ** np.random.uniform(0, 4, size=150))
        res_wide = auth.test_benford(wide_data)
        self.assertTrue(res_wide["is_applicable"])

    def test_benford_conformance_and_violation(self):
        """
        Tests if Benford's Law test correctly flags uniform leading digits but passes natural log-normal digits.
        """
        # 1. Conforming data: Log-normal spans multiple orders of magnitude
        conforming_data = pd.Series(np.random.lognormal(mean=2, sigma=2, size=500))
        auth = DatasetAuthenticator(pd.DataFrame({"col": conforming_data}))
        res_conf = auth.test_benford(conforming_data)
        
        # Log-normal should generally pass Benford (p-value > 0.01 or at least suspicion score is low)
        if res_conf["is_applicable"]:
            self.assertLess(res_conf["suspicion_score"], 0.7)

        # 2. Violating data: Uniform leading digits (e.g. values forced to start with 5)
        # e.g. 5, 50, 500, 5000, etc.
        violating_vals = []
        for _ in range(200):
            scale = 10 ** np.random.randint(0, 4)
            violating_vals.append(np.random.uniform(5.0, 5.99) * scale)
        violating_data = pd.Series(violating_vals)
        
        res_viol = auth.test_benford(violating_data)
        if res_viol["is_applicable"]:
            # Chi-square should reject Benford
            self.assertEqual(res_viol["status"], "Flagged")
            self.assertGreater(res_viol["suspicion_score"], 0.5)

    def test_sensor_artifacts_entropy(self):
        """
        Tests if the mantissa entropy check distinguishes high-precision floats (AI generated)
        from low-precision rounded values (sensor measurements).
        """
        # 1. Rounded data (sensor-like): 1 decimal place
        rounded_data = pd.Series(np.round(np.random.uniform(10, 100, size=200), 1))
        auth = DatasetAuthenticator(pd.DataFrame({"col": rounded_data}))
        res_rounded = auth.test_sensor_artifacts(rounded_data)
        
        # Rounded data should have very low decimal entropy and be flagged as Normal / Quantized
        self.assertLess(res_rounded["decimal_entropy"], 1.0)
        self.assertNotEqual(res_rounded["status"], "Suspicious (High Entropy/No Discretization)")

        # 2. High-precision continuous data (AI/Synthetic-like)
        raw_floats = pd.Series(np.random.uniform(10, 100, size=200))
        res_raw = auth.test_sensor_artifacts(raw_floats)
        
        # High precision floats should have high entropy (close to log2(10) ~ 3.32)
        self.assertGreater(res_raw["decimal_entropy"], 2.8)
        self.assertEqual(res_raw["status"], "Suspicious (High Entropy/No Discretization)")

    def test_residuals_and_normality(self):
        """
        Tests the residuals analysis.
        """
        # Data with perfectly linear trend + perfect Gaussian white noise
        x = np.arange(100)
        y = 2 * x + np.random.normal(0, 1, size=100)
        auth = DatasetAuthenticator(pd.DataFrame({"col": y}))
        res = auth.test_residuals(pd.Series(y))
        
        self.assertTrue(res["is_applicable"])
        # Should execute successfully without throwing errors
        self.assertIn("dw_stat", res)
        self.assertIn("shapiro_p", res)

    def test_bivariate_relationships(self):
        """
        Tests bivariate tests like perfect correlation check.
        """
        # Generate perfect linear dependency: y = 3 * x
        x = np.random.uniform(0, 10, size=100)
        y = 3 * x
        
        df = pd.DataFrame({"x": x, "y": y})
        auth = DatasetAuthenticator(df)
        res = auth.test_bivariate_and_structural()
        
        # Correlation should be perfect
        corr_info = res["correlations"][0]
        self.assertTrue(corr_info["is_perfect_line"])
        self.assertGreater(corr_info["r_squared"], 0.9999)
        
        # Homoscedasticity check for this pair should flag it
        homo_info = res["homoscedasticity"][0]
        self.assertEqual(homo_info["status"], "Flagged")

if __name__ == "__main__":
    unittest.main()
