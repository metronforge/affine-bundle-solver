"""Shared ctypes layout of the existing BSCertifiedResult ABI."""
import ctypes


class Certified(ctypes.Structure):
    _fields_ = [
        ('fast_status', ctypes.c_int), ('fast_certainty', ctypes.c_int),
        ('rank_estimate', ctypes.c_int), ('rank_lo', ctypes.c_int), ('rank_hi', ctypes.c_int),
        ('eta_x', ctypes.c_double), ('certified_status', ctypes.c_int),
        ('eta_status', ctypes.c_double), ('generator_code', ctypes.c_int),
        ('verifier_code', ctypes.c_int), ('accepted_status_mask', ctypes.c_int),
        ('eta_unique', ctypes.c_double), ('eta_infinite', ctypes.c_double),
        ('eta_inconsistent', ctypes.c_double), ('unique_generator_code', ctypes.c_int),
        ('unique_verifier_code', ctypes.c_int), ('infinite_generator_code', ctypes.c_int),
        ('infinite_verifier_code', ctypes.c_int), ('inconsistent_generator_code', ctypes.c_int),
        ('inconsistent_verifier_code', ctypes.c_int)]
